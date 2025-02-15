from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field, validator
import logging
from typing import Optional
from datetime import datetime
from ..models import UserVerdictEnum  # Ensure this import is correct
from ..dependencies import supabase  # Import supabase client

logger = logging.getLogger(__name__)

class FeedbackRequest(BaseModel):
    feedback_text: str = Field(..., alias="FeedbackText")
    user_verdict: UserVerdictEnum = Field(..., alias="UserVerdict")
    user_id: Optional[int] = Field(None, alias="UserID")
    result_id: Optional[int] = Field(None, alias="ResultID")

    class Config:
        populate_by_name = True

    @validator('feedback_text')
    def validate_feedback(cls, v):
        if isinstance(v, dict):
            if 'FeedbackText' in v:
                return v['FeedbackText']
        return v

router = APIRouter(
    prefix="/api/feedback",
    tags=["feedback"]
)

@router.post("/submit")
async def submit_feedback(feedback_data: FeedbackRequest):
    try:
        # Extract the actual feedback text if it's nested
        feedback_text = feedback_data.feedback_text
        if isinstance(feedback_text, dict) and 'FeedbackText' in feedback_text:
            feedback_text = feedback_text['FeedbackText']

        data = {
            "feedback_text": feedback_text,
            "user_verdict": feedback_data.user_verdict.value,
            "user_id": feedback_data.user_id,
            "result_id": feedback_data.result_id,
            "feedback_date": datetime.utcnow().isoformat()
        }

        logger.debug(f"Inserting data: {data}")
        
        response = supabase.table("feedback").insert(data).execute()
        
        if not response.data:
            logger.error(f"Supabase error: {response}")
            raise HTTPException(status_code=400, detail="Failed to insert feedback")

        return {
            "status": "success",
            "message": "Feedback submitted successfully",
            "data": response.data[0]
        }

    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit feedback: {str(e)}"
        )
