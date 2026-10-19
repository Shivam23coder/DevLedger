"""
GitHub agent: pulls a user's public repos and turns each one into
structured evidence (languages, CI presence, tests, docs) that the
gap detector can later check resume claims against.

Uses the public REST API directly - no OAuth needed for public data.
Set GITHUB_TOKEN in .env to raise the rate limit from 60/hr to 5000/hr.
"""
import asyncio
import datetime
import base64
import json
import logging
import random
import httpx
import redis.asyncio as aioredis
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"

# Initialize Redis client (graceful fallback if connection fails or URL not provided)
redis_client = None
if settings.redis_url:
    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to initialize Redis client at {settings.redis_url}: {e}")


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


async def _get_with_retry(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    max_retries = 3
    base_delay = 1.0  # seconds
    
    headers = _headers()
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
        
    for attempt in range(max_retries + 1):
        try:
            resp = await client.get(url, headers=headers, **kwargs)

            # If token is invalid/expired (401), drop Authorization header and retry unauthenticated
            if resp.status_code == 401 and "Authorization" in headers:
                logger.warning(f"GitHub token returned 401 Unauthorized for {url}. Retrying unauthenticated...")
                headers.pop("Authorization", None)
                resp = await client.get(url, headers=headers, **kwargs)

            # Check if we should retry based on status code
            if resp.status_code in [429, 502, 503, 504]:
                if attempt == max_retries:
                    resp.raise_for_status()
                
                # Read retry-after header if present
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = float(retry_after)
                else:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                
                logger.warning(
                    f"Rate limited or server error ({resp.status_code}) on {url}. "
                    f"Retrying in {delay:.2f}s (Attempt {attempt+1}/{max_retries})..."
                )
                await asyncio.sleep(delay)
                continue
            
            return resp
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            if attempt == max_retries:
                raise
            
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.warning(
                f"Request error {exc} on {url}. "
                f"Retrying in {delay:.2f}s (Attempt {attempt+1}/{max_retries})..."
            )
            await asyncio.sleep(delay)
            
    # Fallback to raise for status in case loop exits without return
    raise httpx.HTTPError("Failed after maximum retries")


async def fetch_repos(client: httpx.AsyncClient, username: str, fetch_limit: int = 5) -> list[dict]:
    """Fetch a user's most recently updated public repos.

    Fetches up to ``fetch_limit`` repos (default 5).
    """
    url = f"{GITHUB_API}/users/{username}/repos"
    params = {"sort": "updated", "per_page": fetch_limit}

    resp = await _get_with_retry(client, url, params=params)
    if resp.status_code == 403:
        raise HTTPException(
            status_code=429,
            detail="GitHub API rate limit exceeded (60 req/hr). Add a valid GITHUB_TOKEN to backend/.env to increase limit to 5,000 req/hr."
        )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"GitHub user '{username}' not found.")
    resp.raise_for_status()
    return resp.json()


def _select_relevant_repos(repos: list[dict], top_n: int = 5) -> list[dict]:
    """Prioritize repositories and return the top *top_n*.

    Sorting criteria (in order of importance):
    1️⃣ Most recent ``updated_at`` (newer first)
    2️⃣ Non‑forked repositories (``fork`` == False) before forks
    3️⃣ Higher star count (``stargazers_count``)

    The function safely parses ``updated_at`` strings to ``datetime`` objects.
    """
    def repo_score(repo: dict):
        # Parse updated_at; fallback to epoch if missing/invalid
        try:
            updated = datetime.datetime.fromisoformat(repo.get("updated_at").replace('Z', '+00:00'))
        except Exception:
            updated = datetime.datetime.min
        # Non‑fork gets higher priority (False -> 0, True -> 1)
        fork_priority = 0 if not repo.get("fork", False) else 1
        stars = repo.get("stargazers_count", 0)
        # Return a tuple that sorts descending by updated, then ascending fork, then descending stars
        return (-updated.timestamp(), fork_priority, -stars)

    sorted_repos = sorted(repos, key=repo_score)
    return sorted_repos[:top_n]



async def _fetch_repo_file_paths(client: httpx.AsyncClient, username: str, repo: str, default_branch: str = "main") -> set[str] | None:
    """Fetch the full list of file paths in the repo via GitHub's Git Trees API.
    Returns a set of lowercase paths, or None if the tree cannot be fetched (e.g. empty repo)."""
    url = f"{GITHUB_API}/repos/{username}/{repo}/git/trees/{default_branch}?recursive=1"
    try:
        resp = await _get_with_retry(client, url)
        if resp.status_code == 200:
            data = resp.json()
            return {item.get("path", "").lower() for item in data.get("tree", []) if item.get("path")}
    except Exception as e:
        logger.debug(f"Could not fetch git tree for {repo}: {e}")
    return None


async def _repo_has_path(client: httpx.AsyncClient, username: str, repo: str, path: str) -> bool:
    """Check if a given path exists in the repo's default branch, without
    downloading the whole repo."""
    url = f"{GITHUB_API}/repos/{username}/{repo}/contents/{path}"
    try:
        resp = await _get_with_retry(client, url)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Error checking path {path} in repo {repo}: {e}")
        return False


async def _extract_repo_dependencies(
    client: httpx.AsyncClient, username: str, repo: str, paths: set[str] | None = None
) -> list[str]:
    """Fetch and extract package dependency names from requirements.txt, pyproject.toml, package.json, go.mod.
    If `paths` is provided, skips fetching manifests that don't exist in the repo."""
    deps = set()

    # 1. requirements.txt
    if paths is None or "requirements.txt" in paths:
        try:
            resp = await _get_with_retry(client, f"{GITHUB_API}/repos/{username}/{repo}/contents/requirements.txt")
            if resp.status_code == 200:
                content_json = resp.json()
                if "content" in content_json:
                    raw_text = base64.b64decode(content_json["content"]).decode("utf-8", errors="ignore")
                    for line in raw_text.splitlines():
                        line = line.strip().split("#")[0].strip()
                        if line and not line.startswith("-"):
                            pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split("[")[0].strip()
                            if pkg:
                                deps.add(pkg.lower())
        except Exception as e:
            logger.debug(f"Could not parse requirements.txt for {repo}: {e}")

    # 2. package.json
    if paths is None or "package.json" in paths:
        try:
            resp = await _get_with_retry(client, f"{GITHUB_API}/repos/{username}/{repo}/contents/package.json")
            if resp.status_code == 200:
                content_json = resp.json()
                if "content" in content_json:
                    raw_text = base64.b64decode(content_json["content"]).decode("utf-8", errors="ignore")
                    pkg_data = json.loads(raw_text)
                    for key in ["dependencies", "devDependencies", "peerDependencies"]:
                        if key in pkg_data and isinstance(pkg_data[key], dict):
                            for pkg in pkg_data[key].keys():
                                deps.add(pkg.lower())
        except Exception as e:
            logger.debug(f"Could not parse package.json for {repo}: {e}")

    # 3. pyproject.toml
    if paths is None or "pyproject.toml" in paths:
        try:
            resp = await _get_with_retry(client, f"{GITHUB_API}/repos/{username}/{repo}/contents/pyproject.toml")
            if resp.status_code == 200:
                content_json = resp.json()
                if "content" in content_json:
                    raw_text = base64.b64decode(content_json["content"]).decode("utf-8", errors="ignore")
                    for line in raw_text.splitlines():
                        line_clean = line.strip().lower()
                        for target in ["fastapi", "torch", "sqlalchemy", "pydantic", "pytest", "django", "flask", "celery", "redis", "passlib", "pyjwt"]:
                            if target in line_clean:
                                deps.add(target)
        except Exception as e:
            logger.debug(f"Could not parse pyproject.toml for {repo}: {e}")

    # 4. go.mod
    if paths is None or "go.mod" in paths:
        try:
            resp = await _get_with_retry(client, f"{GITHUB_API}/repos/{username}/{repo}/contents/go.mod")
            if resp.status_code == 200:
                content_json = resp.json()
                if "content" in content_json:
                    raw_text = base64.b64decode(content_json["content"]).decode("utf-8", errors="ignore")
                    for line in raw_text.splitlines():
                        parts = line.strip().split()
                        if len(parts) >= 2 and ("/" in parts[0] or "/" in parts[1]):
                            pkg_path = parts[0] if "/" in parts[0] else parts[1]
                            pkg_name = pkg_path.split("/")[-1].lower()
                            deps.add(pkg_name)
        except Exception as e:
            logger.debug(f"Could not parse go.mod for {repo}: {e}")

    return sorted(list(deps))


async def _get_ci_workflow_status(client: httpx.AsyncClient, username: str, repo: str) -> dict:
    """Fetch GitHub Actions workflow runs and calculate pass rate and status."""
    url = f"{GITHUB_API}/repos/{username}/{repo}/actions/runs"
    try:
        resp = await _get_with_retry(client, url, params={"per_page": 5})
        if resp.status_code == 200:
            data = resp.json()
            runs = data.get("workflow_runs", [])
            if not runs:
                return {"ci_status": "no_runs", "ci_pass_rate": None, "recent_runs_count": 0}

            completed_runs = [r for r in runs if r.get("status") == "completed"]
            if not completed_runs:
                return {"ci_status": "in_progress", "ci_pass_rate": None, "recent_runs_count": len(runs)}

            successful_runs = [r for r in completed_runs if r.get("conclusion") == "success"]
            pass_rate = round(len(successful_runs) / len(completed_runs), 2)
            latest_status = "passing" if completed_runs[0].get("conclusion") == "success" else "failing"

            return {
                "ci_status": latest_status,
                "ci_pass_rate": pass_rate,
                "recent_runs_count": len(completed_runs)
            }
    except Exception as e:
        logger.debug(f"Could not fetch workflow runs for {repo}: {e}")
    return {"ci_status": "unknown", "ci_pass_rate": None, "recent_runs_count": 0}


async def _get_commit_status(client: httpx.AsyncClient, username: str, repo: str, default_branch: str = "main") -> str:
    """Fetch combined status for the default branch (external CI checks)."""
    url = f"{GITHUB_API}/repos/{username}/{repo}/commits/{default_branch}/status"
    try:
        resp = await _get_with_retry(client, url)
        if resp.status_code == 200:
            state = resp.json().get("state")
            return state if state else "unknown"
    except Exception as e:
        logger.debug(f"Could not fetch commit status for {repo}: {e}")
    return "unknown"


async def _get_cached_repo(repo_name: str, updated_at: str) -> dict | None:
    global redis_client
    if not redis_client or not updated_at:
        return None
    try:
        key = f"repo:{repo_name}:{updated_at}"
        cached = await redis_client.get(key)
        if cached:
            logger.info(f"Cache hit for repo: {repo_name}")
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}). Disabling cache for this session.")
        redis_client = None
    return None


async def _cache_repo(repo_name: str, updated_at: str, data: dict):
    global redis_client
    if not redis_client or not updated_at:
        return
    try:
        key = f"repo:{repo_name}:{updated_at}"
        # Cache for 24 hours (86400 seconds)
        await redis_client.setex(key, 86400, json.dumps(data))
        logger.info(f"Cached data for repo: {repo_name}")
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}). Disabling cache for this session.")
        redis_client = None


async def analyze_repo(client: httpx.AsyncClient, username: str, repo: dict) -> dict:
    """Turn one raw GitHub API repo object into structured evidence."""
    name = repo["name"]
    updated_at = repo.get("updated_at")
    default_branch = repo.get("default_branch", "main")

    # Try cache first
    cached_data = await _get_cached_repo(name, updated_at)
    if cached_data:
        return cached_data

    # Languages breakdown task
    async def get_languages():
        try:
            lang_resp = await _get_with_retry(client, f"{GITHUB_API}/repos/{username}/{name}/languages")
            return list(lang_resp.json().keys()) if lang_resp.status_code == 200 else []
        except Exception as e:
            logger.error(f"Error fetching languages for {name}: {e}")
            return []

    # Fetch languages, file tree, and commit status concurrently
    languages, paths, commit_status = await asyncio.gather(
        get_languages(),
        _fetch_repo_file_paths(client, username, name, default_branch),
        _get_commit_status(client, username, name, default_branch),
    )

    if paths is not None:
        # Fast path: check file presences in-memory from the tree
        has_readme = any(p in paths for p in ("readme.md", "readme", "readme.txt", "readme.rst"))
        has_ci = any(p.startswith(".github/workflows/") for p in paths)
        has_tests = any(p.startswith("tests/") or p.startswith("test/") or p == "tests" or p == "test" for p in paths)
        has_dockerfile = "dockerfile" in paths
        has_makefile = "makefile" in paths

        # Only check dependencies for manifest files that actually exist, and CI status only if workflows exist
        deps_task = _extract_repo_dependencies(client, username, name, paths)
        ci_status_task = _get_ci_workflow_status(client, username, name) if has_ci else asyncio.sleep(0, result={"ci_status": "no_runs", "ci_pass_rate": None, "recent_runs_count": 0})

        dependencies, ci_workflow_info = await asyncio.gather(deps_task, ci_status_task)
    else:
        # Fallback path if git tree could not be retrieved
        readme_task = _repo_has_path(client, username, name, "README.md")
        ci_task = _repo_has_path(client, username, name, ".github/workflows")
        tests_task_1 = _repo_has_path(client, username, name, "tests")
        tests_task_2 = _repo_has_path(client, username, name, "test")
        deps_task = _extract_repo_dependencies(client, username, name, None)
        ci_status_task = _get_ci_workflow_status(client, username, name)
        dockerfile_task = _repo_has_path(client, username, name, "Dockerfile")
        makefile_task = _repo_has_path(client, username, name, "Makefile")

        (
            has_readme, has_ci, has_tests_1, has_tests_2,
            dependencies, ci_workflow_info, has_dockerfile, has_makefile
        ) = await asyncio.gather(
            readme_task, ci_task, tests_task_1, tests_task_2,
            deps_task, ci_status_task, dockerfile_task, makefile_task
        )
        has_tests = has_tests_1 or has_tests_2

    build_configs = []
    if has_dockerfile:
        build_configs.append("Dockerfile")
    if has_makefile:
        build_configs.append("Makefile")

    result = {
        "name": name,
        "primary_language": repo.get("language"),
        "languages": languages,
        "topics": repo.get("topics", []),
        "description": repo.get("description"),
        "dependencies": dependencies,
        "has_readme": has_readme,
        "has_ci": has_ci,
        "ci_status": ci_workflow_info.get("ci_status", "no_runs"),
        "ci_pass_rate": ci_workflow_info.get("ci_pass_rate"),
        "latest_commit_status": commit_status,
        "has_tests": has_tests,
        "build_configs": build_configs,
        "stars": repo.get("stargazers_count", 0),
        "updated_at": updated_at,
    }

    # Store in cache
    await _cache_repo(name, updated_at, result)

    return result



async def analyze_user(username: str, client: httpx.AsyncClient | None = None, fetch_limit: int = 5, top_n: int = 5) -> list[dict]:
    """Full pipeline: fetch up to ``fetch_limit`` repos, prioritize them, and deep‑analyse the top ``top_n`` (5).
    """
    if client is None:
        async with httpx.AsyncClient() as new_client:
            repos = await fetch_repos(new_client, username, fetch_limit)
            selected = _select_relevant_repos(repos, top_n)
            return await _analyze_user_with_client(username, new_client, selected)
    else:
        repos = await fetch_repos(client, username, fetch_limit)
        selected = _select_relevant_repos(repos, top_n)
        return await _analyze_user_with_client(username, client, selected)

# Adjust the helper to accept a pre‑filtered list of repos
async def _analyze_user_with_client(username: str, client: httpx.AsyncClient, repos: list[dict]) -> list[dict]:
    tasks = [analyze_repo(client, username, repo) for repo in repos]
    return await asyncio.gather(*tasks)
