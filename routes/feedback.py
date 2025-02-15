from fastapi import APIRouter, HTTPException, Request
from supabase import create_client
from config import settings
from pydantic import BaseModel
import logging

class FeedbackInput(BaseModel):
    feedback: str

router = APIRouter()
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

logging.basicConfig(level=logging.INFO)

@router.post("/feedback")
async def submit_feedback(feedback_input: FeedbackInput):
    if not feedback_input.feedback.strip():
        raise HTTPException(status_code=400, detail="Feedback cannot be empty")
        
    try:
        data = {
            'content': feedback_input.feedback.strip(),
        }
        
        response = supabase.table('feedback').insert(data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to store feedback")
            
        return {
            "status": "success",
            "message": "Feedback submitted successfully",
            "data": response.data[0]
        }
            
    except Exception as e:
        logging.error(f"Error submitting feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error submitting feedback: {str(e)}")
