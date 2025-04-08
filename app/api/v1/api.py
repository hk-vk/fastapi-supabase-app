from fastapi import APIRouter
from app.api.v1.endpoints import exa_service, image_analysis

api_router = APIRouter()
api_router.include_router(exa_service.router, prefix="/exa-service", tags=["exa-service"])
api_router.include_router(image_analysis.router, prefix="/image-analysis", tags=["image-analysis"]) 