from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AnalysisRequestCreate(BaseModel):
    content_type: str
    content: str
    user_id: Optional[str] = None

class AnalysisRequestResponse(BaseModel):
    id: int
    content_type: str
    content: str
    user_id: Optional[str]
    submission_date: datetime

class FeedbackCreate(BaseModel):
    feedback: str