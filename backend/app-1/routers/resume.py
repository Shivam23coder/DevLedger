from fastapi import APIRouter, UploadFile, File, HTTPException

from app.agents.resume_agent import parse_resume

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/parse")
async def parse_resume_endpoint(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported in v1.")

    pdf_bytes = await file.read()
    try:
        result = parse_resume(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse PDF: {e}")

    return result
