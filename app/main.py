from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from app.services.news_analysis import NewsAnalysisService
import asyncio

app = FastAPI()

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

# ...rest of existing code...