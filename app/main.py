from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from app.services.news_analysis import NewsAnalysisService
from app.api.v1.api import api_router
import asyncio
import os

app = FastAPI(
    title="Image Analysis API",
    description="API for analyzing images using Gemini AI",
    version="1.0.0"
)

# Include all API routers
app.include_router(api_router, prefix="/api/v1")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure timeout settings
@app.middleware("http")
async def timeout_middleware(request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=120)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"detail": "Request timeout"}
        )

# Initialize services
news_service = NewsAnalysisService()

@app.on_event("startup")
async def startup_event():
    # Initialize persistent sessions on startup
    await news_service.get_session()
    await news_service.get_translate_session()

@app.on_event("shutdown")
async def shutdown_event():
    # Cleanup sessions on shutdown
    await news_service.cleanup()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)