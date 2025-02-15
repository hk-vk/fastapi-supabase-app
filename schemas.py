from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class ContentTypeEnum(str, Enum):
    TEXT = "TEXT"
    URL = "URL"
    IMAGE = "IMAGE"

class AnalysisRequestCreate(BaseModel):
    content_type: ContentTypeEnum
    content: str
    user_id: Optional[int] = None

    class Config:
        orm_mode = True 

class AnalysisRequestResponse(BaseModel):
    id: int
    content_type: ContentTypeEnum
    content: str
    user_id: Optional[int]
    submission_date: datetime

    class Config:
        orm_mode = True

class FeedbackCreate(BaseModel):
    feedback: str

    class Config:
        orm_mode = True
