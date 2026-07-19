import asyncio
import httpx

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.agents.github_agent import analyze_user
from app.agents.resume_agent import parse_resume
from app.agents.dsa_agent import analyze_dsa
from app.services.gap_detector import find_gaps, find_unverified
from app.services.narrative_advisor import generate_narrative_advice
from app.models import Profile, Repository, ResumeClaim, Gap
from app.schemas import ProfileAnalysisOut


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

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("/analyze", response_model=ProfileAnalysisOut)
async def analyze_profile(
    github_username: str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """End-to-end v1 flow:
    1. Analyze GitHub repos (evidence layer)
    2. Parse resume for claimed skills + profile links
    3. Run rule-based gap detection between the two
    4. Persist everything to the profile store
    """
    if not resume.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported in v1.")

    # 1. GitHub evidence
    try:
        async with httpx.AsyncClient() as client:
            repos = await analyze_user(github_username, client=client, limit=10)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub analysis failed: {e}")

    # 2. Resume claims + links
    pdf_bytes = await resume.read()
    try:
        resume_data = parse_resume(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse resume PDF: {e}")

    claimed_skills = resume_data["claimed_skills"]
    skill_details = resume_data.get("skill_details", [])
    detected_links = resume_data["detected_links"]

    # Extract usernames for DSA APIs
    leetcode_url = detected_links.get("leetcode")
    codeforces_url = detected_links.get("codeforces")
    codechef_url = detected_links.get("codechef")
    
    leetcode_user = _extract_username_from_url(leetcode_url)
    codeforces_user = _extract_username_from_url(codeforces_url)
    codechef_user = _extract_username_from_url(codechef_url)

    # Fetch DSA stats
    dsa_evidence = {"leetcode": None, "codeforces": None, "codechef": None}
    try:
        async with httpx.AsyncClient() as client:
            dsa_evidence = await analyze_dsa(leetcode_user, codeforces_user, codechef_user, client)
    except Exception as e:
        print(f"DSA analysis failed: {e}")

    # 3. Gap detection (rule-based)
    gaps = find_gaps(claimed_skills, repos, dsa_evidence)

    # 3b. Narrative advice (LLM reasoning layer) - runs in a thread since the
    # anthropic SDK client here is synchronous; degrades to None on any
    # failure or missing API key, never blocks the rest of the analysis.
    narrative_advice = await asyncio.to_thread(generate_narrative_advice, gaps, repos, claimed_skills)

    # 4. Persist (upsert profile by github_username)
    profile = db.query(Profile).filter_by(github_username=github_username).first()
    if not profile:
        profile = Profile(github_username=github_username)
        db.add(profile)
        db.flush()  # get profile.id before inserting children
    else:
        # Clear previous analysis so re-running doesn't duplicate rows
        db.query(Repository).filter_by(profile_id=profile.id).delete()
        db.query(ResumeClaim).filter_by(profile_id=profile.id).delete()
        db.query(Gap).filter_by(profile_id=profile.id).delete()

    profile.linkedin_url = detected_links.get("linkedin")
    profile.leetcode_username = leetcode_url
    profile.codeforces_username = codeforces_url
    profile.codechef_username = codechef_url
    profile.leetcode_stats = dsa_evidence.get("leetcode")
    profile.codeforces_stats = dsa_evidence.get("codeforces")
    profile.codechef_stats = dsa_evidence.get("codechef")
    profile.narrative_advice = narrative_advice

    for repo in repos:
        db.add(Repository(
            profile_id=profile.id,
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

    for skill in claimed_skills:
        db.add(ResumeClaim(profile_id=profile.id, skill=skill))

    for gap in gaps:
        db.add(Gap(
            profile_id=profile.id,
            skill=gap["skill"],
            reason=gap["reason"],
            suggestion=gap["suggestion"],
        ))

    db.commit()

    return ProfileAnalysisOut(
        github_username=github_username,
        repositories=repos,
        claimed_skills=claimed_skills,
        skill_details=skill_details,
        gaps=gaps,
        unverified_skills=find_unverified(claimed_skills),
        narrative_advice=narrative_advice,
        detected_links=detected_links,
        leetcode_stats=dsa_evidence.get("leetcode"),
        codeforces_stats=dsa_evidence.get("codeforces"),
        codechef_stats=dsa_evidence.get("codechef"),
    )


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
