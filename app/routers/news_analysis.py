from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.schemas import NewsAnalysisRequest
from app.services.news_analysis import NewsAnalysisService
import json
from typing import Dict, Any
from fastapi import Query

router = APIRouter()
news_analysis_service = NewsAnalysisService()

@router.post("/reverse-searchy")
async def analyze_news(
    request: NewsAnalysisRequest, 
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Analyze news text in Malayalam language.
    
    Args:
        request: NewsAnalysisRequest containing Malayalam text in the query field
        background_tasks: FastAPI background tasks
        
    Returns:
        Dict containing analysis results with fields:
        - ISFAKE: 0 or 1
        - CONFIDENCE: float between 0 and 1
        - EXPLANATION: String explaining the analysis
    """
    try:
        if not request.query:
            raise HTTPException(status_code=400, detail="Query text is required")
            
        result = await news_analysis_service.analyze_news(request.query, background_tasks)
        return result if isinstance(result, dict) else json.loads(result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))