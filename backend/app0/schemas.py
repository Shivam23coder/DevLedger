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
