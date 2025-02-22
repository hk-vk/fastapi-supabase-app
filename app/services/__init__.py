"""
Services package initialization
"""
from app.services.writing_style import get_analyzer
from app.services.news_analysis import NewsAnalysisService

__all__ = [
    'get_analyzer',
    'NewsAnalysisService'
]