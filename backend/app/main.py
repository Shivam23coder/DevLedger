from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import github, resume, profile

# Schema is managed by Alembic migrations (see alembic/), not auto-created
# here. Run `alembic upgrade head` before first startup, and again after
# pulling any change that adds/modifies a model field - this is exactly
# what caused the earlier "column does not exist" crash when narrative_advice
# was added without a migration.

app = FastAPI(
    title="EngineerOS API",
    description="v1: GitHub Intelligence + Resume Gap Analysis",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(github.router)
app.include_router(resume.router)
app.include_router(profile.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "EngineerOS API v1"}
