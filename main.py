import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from supabase import create_client, Client
from app.schemas import AnalysisRequestCreate, AnalysisRequestResponse, FeedbackCreate
from app.routers import feedback
from app.services.news_analysis import NewsAnalysisService
from app.services import get_analyzer
from typing import Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv, dotenv_values
import logging
from app.core.http_client import get_http_session, cleanup_http_session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

# Application lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize services and create HTTP session
    app.state.http_session = await get_http_session()
    app.state.news_service = NewsAnalysisService()
    app.state.writing_style_analyzer = get_analyzer()
    
    yield
    
    # Shutdown: Cleanup resources
    await cleanup_http_session()
    if hasattr(app.state, 'news_service'):
        await app.state.news_service.cleanup()

# Initialize FastAPI app with ORJSON response and lifecycle management
app = FastAPI(
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
    title="YEAH News Detection API",
    description="API for analyzing news articles with persistent connections"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400
)

# Include routers
app.include_router(feedback.router, prefix="/api")

# Initialize Supabase client with debug logging
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

logger.debug(f"SUPABASE_URL: {'set' if SUPABASE_URL else 'not set'}")
logger.debug(f"SUPABASE_KEY: {'set' if SUPABASE_KEY else 'not set'}")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Try loading directly from .env file as fallback
    config = dotenv_values(".env")
    SUPABASE_URL = config.get("SUPABASE_URL")
    SUPABASE_KEY = config.get("SUPABASE_KEY")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/")
async def root():
    return {"status": "healthy"}

@app.post("/analysis_requests/", response_model=AnalysisRequestResponse)
async def create_analysis_request(request: AnalysisRequestCreate):
    try:
        data = {
            "content_type": request.content_type,
            "content": request.content,
            "user_id": request.user_id,
            "submission_date": datetime.utcnow().isoformat()
        }
        response = supabase.table("analysis_requests").insert(data).execute()
        if response.status_code != 201:
            raise HTTPException(status_code=400, detail="Failed to create analysis request")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/feedback")
async def create_feedback(feedback: FeedbackCreate):
    try:
        data = {
            "feedback_text": feedback.feedback,
            "created_at": datetime.utcnow().isoformat()
        }
        response = supabase.table("feedback").insert(data).execute()
        if response.status_code != 201:
            raise HTTPException(status_code=400, detail="Failed to submit feedback")
        return {"status": "success", "message": "Feedback submitted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/reverse-searchy")
async def reverse_search(query: Dict[str, Any], background_tasks: BackgroundTasks):
    try:
        result = await app.state.news_service.analyze_news(query.get("content", ""), background_tasks)
        return result
    except Exception as e:
        logger.error(f"Error in reverse search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/writing-style")
async def analyze_writing_style(query: Dict[str, str]):
    try:
        content = query.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")
        
        logger.debug(f"Analyzing text of length: {len(content)}")
        result = app.state.writing_style_analyzer.analyze_text(content)
        
        logger.debug(f"Analysis results: {result}")
        if all(score == 0 for score in result.values()):
            logger.warning("All scores returned as zero - possible analysis failure")
            
        return result
    except Exception as e:
        logger.error(f"Error in writing style analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)