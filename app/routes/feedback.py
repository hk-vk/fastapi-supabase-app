from fastapi import APIRouter, HTTPException, status
from ..dependencies import supabase
from ..schemas import FeedbackCreate, FeedbackResponse
from datetime import datetime

router = APIRouter()

@router.post("/submit", response_model=FeedbackResponse)async def submit_feedback(feedback: FeedbackCreate):    print("Feedback submission received")  # Debugging    try:        feedback_data = {            "user_id": feedback.UserID,            "result_id": feedback.ResultID,            "feedback_text": feedback.FeedbackText,            "user_verdict": feedback.UserVerdict,            "feedback_date": datetime.utcnow().isoformat()        }                response = supabase.table('feedback').insert(feedback_data).execute()                if not response.data:            raise HTTPException(                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,                detail="Failed to store feedback"            )                    return response.data[0]            except Exception as e:        raise HTTPException(            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,            detail=f"Error submitting feedback: {str(e)}"        )