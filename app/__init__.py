"""
App module initialization.
"""
from app.services import writing_style, news_analysis
from app.core import http_client
from fastapi import FastAPI
from app.api.v1.api import api_router

__all__ = [
    'writing_style',
    'news_analysis',
    'http_client'
]

app = FastAPI(
    title="Image Analysis API",
    description="API for analyzing images using Gemini AI",
    version="1.0.0"
)

app.include_router(api_router, prefix="/api/v1")
