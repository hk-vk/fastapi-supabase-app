from fastapi import FastAPI, BackgroundTasks, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from app.services.news_analysis import NewsAnalysisService
import asyncio
from typing import Optional
import os
import tempfile

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

@app.post("/analyze")
async def analyze_image(image: UploadFile = File(...), text: Optional[str] = Form(None)):
    try:
        # Create a temporary file to store the uploaded image
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            image_path = temp_file.name
            # Reset file position to beginning after read in previous operation
            await image.seek(0)
            # Write the file content to the temp file
            temp_file.write(await image.read())
        
        try:
            # Perform image analysis
            analysis_result = await news_service.analyze_image(image_path, user_text=text)
            
            # Check if extracted text exists and has more than 10 characters
            extracted_text = analysis_result.get("extracted_text", "")
            extracted_text_reverse_search = None
            
            if extracted_text and len(extracted_text) > 10:
                # Perform reverse search on the extracted text
                try:
                    extracted_text_analysis = await news_service.analyze_text(extracted_text)
                    extracted_text_reverse_search = {
                        "found": bool(extracted_text_analysis.get("matches", [])),
                        "matches": extracted_text_analysis.get("matches", []),
                        "reliability_score": extracted_text_analysis.get("reliability_score", 0)
                    }
                except Exception as text_search_error:
                    print(f"Error during extracted text reverse search: {text_search_error}")
                    extracted_text_reverse_search = {
                        "found": False,
                        "error": str(text_search_error)
                    }
            
            # Build the response
            response = {
                "verdict": analysis_result["verdict"],
                "score": analysis_result["fake_score"],
                "details": {
                    "ai_generated": analysis_result["ai_generated"],
                    "reverse_search": analysis_result["reverse_search"],
                    "deepfake": analysis_result["deepfake"],
                    "tampering_analysis": analysis_result["tampering"],
                    "image_caption": analysis_result["image_caption"],
                }
            }
            
            # Add extracted text analysis if available
            if "extracted_text" in analysis_result and analysis_result["extracted_text"]:
                text_analysis = {
                    "user_text": text,
                    "extracted_text": analysis_result["extracted_text"],
                    "mismatch": analysis_result.get("text_mismatch", False),
                    "context_similarity": round(analysis_result.get("context_similarity", 0), 2),
                    "context_mismatch": analysis_result.get("context_mismatch", False)
                }
                
                # Add text reverse search results if available
                if extracted_text_reverse_search:
                    text_analysis["reverse_search"] = extracted_text_reverse_search
                    
                response["details"]["text_analysis"] = text_analysis

            return response
            
        finally:
            # Clean up temporary file
            if os.path.exists(image_path):
                os.unlink(image_path)
                
    except Exception as e:
        print(f"Error during image analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ...rest of existing code...