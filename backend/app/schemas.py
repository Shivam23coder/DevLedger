from datetime import datetime
from pydantic import BaseModel


class RepositoryOut(BaseModel):
    name: str
    primary_language: str | None
    languages: list[str]
    topics: list[str]
    has_readme: bool
    has_ci: bool
    has_tests: bool
    stars: int

    class Config:
        from_attributes = True


class GapOut(BaseModel):
    skill: str
    reason: str
    suggestion: str | None

    class Config:
        from_attributes = True


class ProfileAnalysisOut(BaseModel):
    github_username: str
    repositories: list[RepositoryOut]
    claimed_skills: list[str]
    skill_details: list[dict] = []   # per-skill confidence scores from resume_agent
    gaps: list[GapOut]
    unverified_skills: list[str]
    narrative_advice: str | None
    detected_links: dict[str, str | None]
    leetcode_stats: dict | None = None
    codeforces_stats: dict | None = None
    codechef_stats: dict | None = None


class HistoryEntryOut(BaseModel):
    """One point on the gap-closure-over-time view. Deliberately just the
    denormalized counts, not full repo/gap detail - the history endpoint
    is for a trend chart, not for reconstructing every past run in full."""
    run_id: int
    created_at: datetime
    evidenced_count: int
    gap_count: int
    unverified_count: int

    class Config:
        from_attributes = True
