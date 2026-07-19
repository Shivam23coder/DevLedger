from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import github, resume, profile

# Creates tables on startup if they don't exist yet.
# Fine for v1; swap for Alembic migrations once the schema stabilizes.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EngineerOS API",
    description="v1: GitHub Intelligence + Resume Gap Analysis",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(github.router)
app.include_router(resume.router)
app.include_router(profile.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "EngineerOS API v1"}
