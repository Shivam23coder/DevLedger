from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Profile(Base):
    """One row per developer - identity only (username, linked accounts).
    Per-run data (repos, gaps, DSA stats, narrative advice) now lives on
    AnalysisRun instead of here, so re-running analysis appends history
    instead of overwriting it."""
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    github_username = Column(String, unique=True, index=True)
    linkedin_url = Column(String, nullable=True)
    leetcode_username = Column(String, nullable=True)
    codeforces_username = Column(String, nullable=True)
    codechef_username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    runs = relationship("AnalysisRun", back_populates="profile", order_by="AnalysisRun.created_at")


class AnalysisRun(Base):
    """One row per /profile/analyze execution. This is what makes history
    possible: each run is preserved rather than overwritten, so gap-closure
    over time can be shown instead of only ever seeing the latest snapshot.

    Summary counts are denormalized here (not recomputed by re-joining
    Gap/ResumeClaim every time) specifically so the history/trend view is
    one cheap query instead of N joins across every past run."""
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    narrative_advice = Column(String, nullable=True)
    leetcode_stats = Column(JSON, nullable=True)
    codeforces_stats = Column(JSON, nullable=True)
    codechef_stats = Column(JSON, nullable=True)

    # Denormalized for the history view - see class docstring
    evidenced_count = Column(Integer, default=0)
    gap_count = Column(Integer, default=0)
    unverified_count = Column(Integer, default=0)

    profile = relationship("Profile", back_populates="runs")
    repositories = relationship("Repository", back_populates="run", cascade="all, delete-orphan")
    resume_claims = relationship("ResumeClaim", back_populates="run", cascade="all, delete-orphan")
    gaps = relationship("Gap", back_populates="run", cascade="all, delete-orphan")


class Repository(Base):
    """One row per analyzed GitHub repo, scoped to a single AnalysisRun -
    every skill claim in that same run gets checked against rows here."""
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), index=True)
    name = Column(String)
    primary_language = Column(String, nullable=True)
    languages = Column(JSON, default=list)
    topics = Column(JSON, default=list)
    description = Column(String, nullable=True)
    has_readme = Column(Boolean, default=False)
    has_ci = Column(Boolean, default=False)
    has_tests = Column(Boolean, default=False)
    stars = Column(Integer, default=0)
    updated_at = Column(DateTime, nullable=True)

    run = relationship("AnalysisRun", back_populates="repositories")


class ResumeClaim(Base):
    """One row per skill the resume claims in a given run."""
    __tablename__ = "resume_claims"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), index=True)
    skill = Column(String, index=True)
    raw_context = Column(String, nullable=True)

    run = relationship("AnalysisRun", back_populates="resume_claims")


class Gap(Base):
    """Output of the recommendation engine's rule-based layer for one run:
    a claimed skill with no supporting evidence that run."""
    __tablename__ = "gaps"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), index=True)
    skill = Column(String)
    reason = Column(String)
    suggestion = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("AnalysisRun", back_populates="gaps")
