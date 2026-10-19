"""
The full analysis pipeline (GitHub + resume + DSA + gaps + LLM advice),
extracted into a Celery task so it runs in a worker process instead of
blocking the FastAPI request thread. See app/routers/profile.py for how
this is enqueued and polled.
"""
import asyncio
import base64

import httpx

from app.celery_app import celery_app
from app.database import SessionLocal
from app.agents.github_agent import analyze_user
from app.agents.resume_agent import parse_resume
from app.agents.dsa_agent import analyze_dsa
from app.services.gap_detector import find_gaps, find_unverified
from app.services.narrative_advisor import generate_narrative_advice
from app.models import Profile, AnalysisRun, Repository, ResumeClaim, Gap


def _extract_username_from_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.rstrip("/")
    parts = url.split("/")
    if len(parts) > 0:
        username = parts[-1]
        if username == "u" and len(parts) > 1:
            username = parts[-2]
        return username
    return None


async def _run_pipeline(github_username: str, resume_bytes: bytes) -> dict:
    # 1. Parse resume first (in-memory CPU parsing, ~20ms)
    resume_data = parse_resume(resume_bytes)
    claimed_skills = resume_data["claimed_skills"]
    skill_details = resume_data.get("skill_details", [])
    detected_links = resume_data["detected_links"]

    leetcode_url = detected_links.get("leetcode")
    codeforces_url = detected_links.get("codeforces")
    codechef_url = detected_links.get("codechef")

    leetcode_user = _extract_username_from_url(leetcode_url)
    codeforces_user = _extract_username_from_url(codeforces_url)
    codechef_user = _extract_username_from_url(codechef_url)

    # 2. Concurrently fetch GitHub repositories and DSA coding profiles in parallel
    async with httpx.AsyncClient() as client:
        async def _safe_analyze_dsa():
            try:
                return await analyze_dsa(leetcode_user, codeforces_user, codechef_user, client)
            except Exception as e:
                print(f"DSA analysis failed: {e}")
                return {"leetcode": None, "codeforces": None, "codechef": None}

        repos, dsa_evidence = await asyncio.gather(
            analyze_user(github_username, client=client, fetch_limit=5, top_n=5),
            _safe_analyze_dsa(),
        )

        gaps = find_gaps(claimed_skills, repos, dsa_evidence)
        unverified_skills = find_unverified(claimed_skills)
        narrative_advice = await generate_narrative_advice(gaps, repos, claimed_skills, client=client)

    return {
        "github_username": github_username,
        "repositories": repos,
        "claimed_skills": claimed_skills,
        "skill_details": skill_details,
        "gaps": gaps,
        "unverified_skills": unverified_skills,
        "narrative_advice": narrative_advice,
        "detected_links": detected_links,
        "leetcode_stats": dsa_evidence.get("leetcode"),
        "codeforces_stats": dsa_evidence.get("codeforces"),
        "codechef_stats": dsa_evidence.get("codechef"),
        "leetcode_url": leetcode_url,
        "codeforces_url": codeforces_url,
        "codechef_url": codechef_url,
    }


def _persist(result: dict) -> None:
    """Creates a new AnalysisRun every call - re-running analysis now
    APPENDS history instead of overwriting the previous result. Profile
    itself only tracks identity (username, linked accounts); everything
    that changes run-to-run lives on the run row."""
    db = SessionLocal()
    try:
        github_username = result["github_username"]
        profile = db.query(Profile).filter_by(github_username=github_username).first()
        if not profile:
            profile = Profile(github_username=github_username)
            db.add(profile)
            db.flush()

        profile.linkedin_url = result["detected_links"].get("linkedin")
        # Store the extracted username (not the full URL) so it displays correctly
        profile.leetcode_username = _extract_username_from_url(result["leetcode_url"])
        profile.codeforces_username = _extract_username_from_url(result["codeforces_url"])
        profile.codechef_username = _extract_username_from_url(result["codechef_url"])

        evidenced_count = len(result["claimed_skills"]) - len(result["gaps"]) - len(result["unverified_skills"])

        run = AnalysisRun(
            profile_id=profile.id,
            narrative_advice=result["narrative_advice"],
            leetcode_stats=result["leetcode_stats"],
            codeforces_stats=result["codeforces_stats"],
            codechef_stats=result["codechef_stats"],
            evidenced_count=max(evidenced_count, 0),
            gap_count=len(result["gaps"]),
            unverified_count=len(result["unverified_skills"]),
        )
        db.add(run)
        db.flush()  # need run.id before attaching children

        for repo in result["repositories"]:
            db.add(Repository(
                run_id=run.id,
                name=repo["name"],
                primary_language=repo["primary_language"],
                languages=repo["languages"],
                topics=repo["topics"],
                description=repo["description"],
                has_readme=repo["has_readme"],
                has_ci=repo["has_ci"],
                has_tests=repo["has_tests"],
                stars=repo["stars"],
            ))

        for skill in result["claimed_skills"]:
            db.add(ResumeClaim(run_id=run.id, skill=skill))

        for gap in result["gaps"]:
            db.add(Gap(
                run_id=run.id,
                skill=gap["skill"],
                reason=gap["reason"],
                suggestion=gap["suggestion"],
            ))

        db.commit()
    finally:
        db.close()


async def run_pipeline_async(github_username: str, resume_bytes: bytes) -> dict:
    result = await _run_pipeline(github_username, resume_bytes)
    try:
        _persist(result)
    except Exception as e:
        print(f"DB persistence skipped/warning: {e}")
    return {k: v for k, v in result.items() if k not in ("leetcode_url", "codeforces_url", "codechef_url")}


@celery_app.task(name="analyze_profile_task")
def analyze_profile_task(github_username: str, resume_b64: str) -> dict:
    resume_bytes = base64.b64decode(resume_b64)
    result = asyncio.run(_run_pipeline(github_username, resume_bytes))
    try:
        _persist(result)
    except Exception as e:
        print(f"DB persistence skipped/warning: {e}")
    # Strip internal-only keys before returning to the client
    return {k: v for k, v in result.items() if k not in ("leetcode_url", "codeforces_url", "codechef_url")}
