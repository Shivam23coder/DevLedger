from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Profile(Base):
    """One row per developer. Anchors everything else."""
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    github_username = Column(String, unique=True, index=True)
    linkedin_url = Column(String, nullable=True)
    leetcode_username = Column(String, nullable=True)
    codeforces_username = Column(String, nullable=True)
    codechef_username = Column(String, nullable=True)
    leetcode_stats = Column(JSON, nullable=True)
    codeforces_stats = Column(JSON, nullable=True)
    codechef_stats = Column(JSON, nullable=True)
    narrative_advice = Column(String, nullable=True)  # LLM-generated, see narrative_advisor.py
    created_at = Column(DateTime, default=datetime.utcnow)

    repositories = relationship("Repository", back_populates="profile")
    resume_claims = relationship("ResumeClaim", back_populates="profile")
    gaps = relationship("Gap", back_populates="profile")


class Repository(Base):
    """One row per analyzed GitHub repo. This is the 'evidence' layer -
    every skill claim gets checked against rows here."""
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"))
    name = Column(String)
    primary_language = Column(String, nullable=True)
    languages = Column(JSON, default=list)       # all languages detected, not just primary
    topics = Column(JSON, default=list)           # github topics/tags
    description = Column(String, nullable=True)
    has_readme = Column(Boolean, default=False)
    has_ci = Column(Boolean, default=False)       # .github/workflows present
    has_tests = Column(Boolean, default=False)    # test dir/files detected
    stars = Column(Integer, default=0)
    updated_at = Column(DateTime, nullable=True)

    profile = relationship("Profile", back_populates="repositories")


class ResumeClaim(Base):
    """One row per skill the resume claims. Gap detection compares this
    against Repository evidence for the same profile."""
    __tablename__ = "resume_claims"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"))
    skill = Column(String, index=True)
    raw_context = Column(String, nullable=True)  # the resume line it came from

    profile = relationship("Profile", back_populates="resume_claims")


class Gap(Base):
    """Output of the recommendation engine's rule-based layer:
    a claimed skill with no supporting evidence in the GitHub repos."""
    __tablename__ = "gaps"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"))
    skill = Column(String)
    reason = Column(String)
    suggestion = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("Profile", back_populates="gaps")
