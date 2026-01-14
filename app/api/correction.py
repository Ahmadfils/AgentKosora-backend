from fastapi import APIRouter
from pydantic import BaseModel
from app.mcp.server import mcp_server

router = APIRouter()

class CorrectionRequest(BaseModel):
    subject: str
    rubric: str
    student_text: str

@router.post("/auto")
def auto_correction(data: CorrectionRequest):
    result = mcp_server.run({
        "subject": data.subject,
        "rubric": data.rubric,
        "student_text": data.student_text
    })
    return result
