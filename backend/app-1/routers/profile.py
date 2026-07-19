import base64

from celery.result import AsyncResult
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.celery_app import celery_app
from app.tasks import analyze_profile_task
from app.services.gap_detector import find_unverified
from app.models import Profile
from app.schemas import ProfileAnalysisOut

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("/analyze", status_code=202)
async def analyze_profile(
    github_username: str = Form(...),
    resume: UploadFile = File(...),
):
    """Enqueues the full pipeline (GitHub + resume + 3 DSA sources + LLM
    advice) as a Celery task instead of blocking the request for it - this
    got noticeably slower once DSA sources were added, making the async
    queue more important, not less.

    Returns immediately with a job_id; poll GET /profile/analyze/status/{job_id}.
    Requires a running Celery worker - see README.
    """
    if not resume.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported in v1.")

    pdf_bytes = await resume.read()
    resume_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    task = analyze_profile_task.delay(github_username, resume_b64)
    return {"job_id": task.id, "status": "queued"}


@router.get("/analyze/status/{job_id}")
def get_analysis_status(job_id: str):
    """Poll this after POST /profile/analyze to get the result once ready."""
    result = AsyncResult(job_id, app=celery_app)

    if result.state == "PENDING":
        return {"status": "pending"}
    if result.state == "FAILURE":
        return {"status": "failed", "error": str(result.result)}
    if result.state == "SUCCESS":
        return {"status": "success", "result": result.result}
    return {"status": result.state.lower()}


@router.get("/{github_username}", response_model=ProfileAnalysisOut)
def get_saved_profile(github_username: str, db: Session = Depends(get_db)):
    """Fetch a previously analyzed profile from storage (no re-analysis)."""
    profile = db.query(Profile).filter_by(github_username=github_username).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found - run /profile/analyze first.")

    return ProfileAnalysisOut(
        github_username=profile.github_username,
        repositories=[{
            "name": r.name, "primary_language": r.primary_language,
            "languages": r.languages, "topics": r.topics,
            "has_readme": r.has_readme, "has_ci": r.has_ci,
            "has_tests": r.has_tests, "stars": r.stars,
        } for r in profile.repositories],
        claimed_skills=[c.skill for c in profile.resume_claims],
        skill_details=[],  # scores not persisted; re-run /profile/analyze to get fresh scores
        gaps=[{"skill": g.skill, "reason": g.reason, "suggestion": g.suggestion} for g in profile.gaps],
        unverified_skills=find_unverified([c.skill for c in profile.resume_claims]),
        narrative_advice=profile.narrative_advice,
        detected_links={
            "github": f"https://github.com/{profile.github_username}",
            "linkedin": profile.linkedin_url,
            "leetcode": profile.leetcode_username,
            "codeforces": profile.codeforces_username,
            "codechef": profile.codechef_username,
        },
        leetcode_stats=profile.leetcode_stats,
        codeforces_stats=profile.codeforces_stats,
        codechef_stats=profile.codechef_stats,
    )
