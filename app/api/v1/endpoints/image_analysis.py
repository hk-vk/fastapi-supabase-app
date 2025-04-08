import os
import tempfile
import requests
import json  # Import the json library
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional
import google.generativeai as genai
from google.generativeai import types

router = APIRouter()

class ImageAnalysisRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[HttpUrl] = None

def is_valid_url(url: str) -> bool:
    try:
        result = requests.head(url, allow_redirects=True, timeout=5)
        return result.status_code == 200
    except:
        return False

def download_image_from_url(url: str) -> str:
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to download image from URL")
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        return temp_file.name

def analyze_image_with_gemini(image_path: str, text: Optional[str] = None) -> dict:
    # Check if API key is set
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_API_KEY environment variable is not set. Please set it to use the image analysis service."
        )

    try:
        # Configure the API key
        genai.configure(api_key=api_key)
        
        # Initialize the model
        model = genai.GenerativeModel('gemini-pro-vision')
        
        # Read image file
        try:
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read image file: {str(e)}"
            )
        
        # Prepare the prompt
        prompt = """Analyze this image and return a detailed analysis in the following EXACT JSON format:

{
    "verdict": "Fake" or "Genuine",
    "score": integer between 0 and 100,
    "details": {
        "ai_generated": boolean,
        "reverse_search": {
            "exists": boolean,
            "matches": array of {url: string, title: string}
        },
        "deepfake": boolean,
        "tampering_analysis": {
            "ela_score": float,
            "edge_score": float,
            "metadata_issues": array of strings,
            "tampered": boolean
        },
        "image_caption": string,
        "text_analysis": {
            "user_text": string or null,
            "extracted_text": string,
            "mismatch": boolean,
            "context_similarity": float,
            "context_mismatch": boolean
        }
    }
}"""

        # Add user text to prompt if provided
        if text:
            prompt += f"\n\nUser provided text for analysis: {text}"

        # Generate content
        response = model.generate_content(
            contents=[prompt, {"mime_type": "image/jpeg", "data": image_data}],
            generation_config={
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
        )
        
        # Clean the response text
        cleaned_text = response.text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:] # Remove ```json
        if cleaned_text.startswith("```"):
             cleaned_text = cleaned_text[3:] # Remove ```
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3] # Remove ```
        cleaned_text = cleaned_text.strip()

        # Parse the cleaned text into JSON
        try:
            analysis_json = json.loads(cleaned_text)
            return analysis_json
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {cleaned_text}") # Log the problematic response
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse analysis response from AI: {str(e)}"
            )

    except Exception as e:
        print(f"Error during image analysis: {str(e)}") # Log the error
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze image: {str(e)}"
        )

@router.post("/analyze")
async def analyze_image(
    image: UploadFile = File(None),
    text: Optional[str] = Form(None),
    url: Optional[str] = Form(None)
):
    image_path = None
    try:
        if image:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
                image_path = temp_file.name
                content = await image.read()
                temp_file.write(content)
        elif url:
            if not is_valid_url(url):
                raise HTTPException(status_code=400, detail="Invalid URL provided")
            image_path = download_image_from_url(url)
        else:
            raise HTTPException(status_code=400, detail="No image file or URL provided")

        raw_analysis_text = analyze_image_with_gemini(image_path, text)
        
        # Clean the response text
        cleaned_text = raw_analysis_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:] # Remove ```json
        if cleaned_text.startswith("```"):
             cleaned_text = cleaned_text[3:] # Remove ```
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3] # Remove ```
        cleaned_text = cleaned_text.strip()

        # Parse the cleaned text into JSON
        try:
            analysis_json = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {cleaned_text}") # Log the problematic response
            raise HTTPException(status_code=500, detail=f"Failed to parse analysis response from AI: {e}")

        # Return the parsed JSON object
        return analysis_json

    except Exception as e:
        # Ensure specific HTTP exceptions are re-raised
        if isinstance(e, HTTPException):
             raise e
        # Raise other exceptions as 500 errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        if image_path and os.path.exists(image_path):
            os.unlink(image_path) 