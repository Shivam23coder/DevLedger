import httpx
from fastapi import APIRouter, HTTPException

from app.agents.github_agent import analyze_user

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/analyze/{username}")
async def analyze_github(username: str, fetch_limit: int = 20, top_n: int = 5):
    try:
        async with httpx.AsyncClient() as client:
            repos = await analyze_user(username, client=client, fetch_limit=fetch_limit, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub analysis failed: {e}")

    return {"username": username, "repositories": repos}
