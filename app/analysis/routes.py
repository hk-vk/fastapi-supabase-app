from fastapi import APIRouter, HTTPException, status
from ..dependencies import supabase
from ..schemas import AnalysisRequestCreate, AnalysisResultCreate, AnalysisRequestResponse, AnalysisResultResponse
from datetime import datetime

router = APIRouter()

@router.post("/store-analysis", response_model=dict)
async def store_analysis(request: AnalysisRequestCreate, result: AnalysisResultCreate):
    try:
        # Store the analysis request
        request_data = {
            "user_id": request.UserID,
            "content_type": request.ContentType,
            "content": request.Content,
            "submission_date": datetime.utcnow().isoformat()
        }
        
        request_response = supabase.table('analysis_requests').insert(request_data).execute()
        
        if not request_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store analysis request"
            )
        
        request_id = request_response.data[0]['request_id']
        
        # Store the analysis result
        result_data = {
            "request_id": request_id,
            "credibility_score": result.CredibilityScore,
            "final_verdict": result.FinalVerdict,
            "analysis_date": datetime.utcnow().isoformat()
        }
        
        result_response = supabase.table('analysis_results').insert(result_data).execute()
        
        if not result_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store analysis result"
            )
            
        return {
            "message": "Analysis stored successfully",
            "request_id": request_id,
            "result_id": result_response.data[0]['result_id']
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error storing analysis: {str(e)}"
        )

@router.get("/get-analysis/{request_id}")
async def get_analysis(request_id: int):
    try:
        # Get the analysis request
        request = supabase.table('analysis_requests')\
            .select("*")\
            .eq('request_id', request_id)\
            .execute()
            
        # Get the corresponding result
        result = supabase.table('analysis_results')\
            .select("*")\
            .eq('request_id', request_id)\
            .execute()
            
        if not request.data or not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
            
        return {
            "request": request.data[0],
            "result": result.data[0]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving analysis: {str(e)}"
        )
