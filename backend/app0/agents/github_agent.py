"""
GitHub agent: pulls a user's public repos and turns each one into
structured evidence (languages, CI presence, tests, docs) that the
gap detector can later check resume claims against.

Uses the public REST API directly - no OAuth needed for public data.
Set GITHUB_TOKEN in .env to raise the rate limit from 60/hr to 5000/hr.
"""
import asyncio
import json
import logging
import random
import httpx
import redis.asyncio as aioredis

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


async def fetch_repos(client: httpx.AsyncClient, username: str, limit: int = 20) -> list[dict]:
    """Fetch a user's most recently updated public repos."""
    url = f"{GITHUB_API}/users/{username}/repos"
    params = {"sort": "updated", "per_page": limit}

    resp = await _get_with_retry(client, url, params=params)
    resp.raise_for_status()
    return resp.json()


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


async def _get_cached_repo(repo_name: str, updated_at: str) -> dict | None:
    if not redis_client or not updated_at:
        return None
    try:
        key = f"repo:{repo_name}:{updated_at}"
        cached = await redis_client.get(key)
        if cached:
            logger.info(f"Cache hit for repo: {repo_name}")
            return json.loads(cached)
    except Exception as e:
        logger.error(f"Redis cache read failed for {repo_name}: {e}")
    return None


async def _cache_repo(repo_name: str, updated_at: str, data: dict):
    if not redis_client or not updated_at:
        return
    try:
        key = f"repo:{repo_name}:{updated_at}"
        # Cache for 24 hours (86400 seconds)
        await redis_client.setex(key, 86400, json.dumps(data))
        logger.info(f"Cached data for repo: {repo_name}")
    except Exception as e:
        logger.error(f"Redis cache write failed for {repo_name}: {e}")


async def analyze_repo(client: httpx.AsyncClient, username: str, repo: dict) -> dict:
    """Turn one raw GitHub API repo object into structured evidence."""
    name = repo["name"]
    updated_at = repo.get("updated_at")

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

    # Run checks in parallel
    languages_task = get_languages()
    readme_task = _repo_has_path(client, username, name, "README.md")
    ci_task = _repo_has_path(client, username, name, ".github/workflows")
    tests_task_1 = _repo_has_path(client, username, name, "tests")
    tests_task_2 = _repo_has_path(client, username, name, "test")

    languages, has_readme, has_ci, has_tests_1, has_tests_2 = await asyncio.gather(
        languages_task, readme_task, ci_task, tests_task_1, tests_task_2
    )

    result = {
        "name": name,
        "primary_language": repo.get("language"),
        "languages": languages,
        "topics": repo.get("topics", []),
        "description": repo.get("description"),
        "has_readme": has_readme,
        "has_ci": has_ci,
        "has_tests": has_tests_1 or has_tests_2,
        "stars": repo.get("stargazers_count", 0),
        "updated_at": updated_at,
    }

    # Store in cache
    await _cache_repo(name, updated_at, result)

    return result


async def _analyze_user_with_client(username: str, client: httpx.AsyncClient, limit: int = 10) -> list[dict]:
    repos = await fetch_repos(client, username, limit=limit)
    tasks = [analyze_repo(client, username, repo) for repo in repos]
    return await asyncio.gather(*tasks)


async def analyze_user(username: str, client: httpx.AsyncClient | None = None, limit: int = 10) -> list[dict]:
    """Full pipeline: fetch repos, then analyze each one.
    Uses concurrency, custom backoff retry, and Redis caching."""
    if client is None:
        async with httpx.AsyncClient() as new_client:
            return await _analyze_user_with_client(username, new_client, limit)
    else:
        return await _analyze_user_with_client(username, client, limit)
