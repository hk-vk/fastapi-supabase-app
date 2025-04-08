# Make app/api/v1 directory a proper Python package 

from app.api.v1.api import api_router

__all__ = ["api_router"] 