from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional
from enum import Enum

class UserCreate(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    first_name: str = ""  # Make it optional with default empty string

class ContentTypeEnum(str, Enum):
    TEXT = "TEXT"
    URL = "URL"
    IMAGE = "IMAGE"

class FinalVerdictEnum(str, Enum):
    REAL = "REAL"
    FAKE = "FAKE"
    UNSURE = "UNSURE"

class UserVerdictEnum(str, Enum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"  # Assign value to DISAGREE

# Analysis Request Models
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

class AnalysisResultCreate(BaseModel):
    RequestID: int
    CredibilityScore: float
    FinalVerdict: FinalVerdictEnum

    model_config = ConfigDict(from_attributes=True)

class AnalysisResultResponse(AnalysisResultCreate):
    ResultID: int

    model_config = ConfigDict(from_attributes=True)

class CredibleSourceCreate(BaseModel):
    SourceURL: str
    CredibilityRating: float
    Domain: str

    model_config = ConfigDict(from_attributes=True)

class CredibleSourceResponse(CredibleSourceCreate):
    SourceID: int
    LastUpdated: datetime

    model_config = ConfigDict(from_attributes=True)

# Feedback Models
class FeedbackCreate(BaseModel):
    feedback: str

class FeedbackResponse(FeedbackCreate):
    FeedbackID: int
    FeedbackDate: datetime

    model_config = ConfigDict(from_attributes=True)

class FakeNewsCreate(BaseModel):
    Headline: str
    Content: str
    SourceURL: str

    model_config = ConfigDict(from_attributes=True)

class FakeNewsResponse(FakeNewsCreate):
    EntryID: int
    DetectedDate: datetime
    CheckCount: int

    model_config = ConfigDict(from_attributes=True)

# News Analysis Models
class NewsAnalysisRequest(BaseModel):
    query: str
    source_lang: Optional[str] = "ml"
    target_lang: Optional[str] = "en"

class NewsAnalysisResponse(BaseModel):
    result: str
