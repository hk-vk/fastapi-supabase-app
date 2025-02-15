from pydantic import BaseModel, Field

class NewsAnalysisRequest(BaseModel):
    query: str = Field(
        ..., 
        description="The news text to analyze. Expected to be in Malayalam language. Will be automatically translated for analysis."
    )

class NewsAnalysisResponse(BaseModel):
    result: dict = Field(
        ...,
        description="Analysis result containing ISFAKE, CONFIDENCE, and EXPLANATION fields"
    )