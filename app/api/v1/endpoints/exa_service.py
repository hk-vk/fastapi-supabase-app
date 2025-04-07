import os
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, HttpUrl
from exa_py import Exa
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

router = APIRouter()

# --- Pydantic Models ---

class ExaRequest(BaseModel):
    url: HttpUrl = Field(..., description="The URL to fetch content for.")

class ExaContentResult(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    publishedDate: Optional[str] = None
    author: Optional[str] = None
    text: Optional[str] = None
    image: Optional[str] = None
    favicon: Optional[str] = None

class ExaContentsResponseData(BaseModel):
    results: List[ExaContentResult]
    requestId: Optional[str] = None
    costDollars: Optional[Dict[str, Any]] = None

class ExaContentsResponse(BaseModel):
    data: ExaContentsResponseData

# --- Dependency ---

def get_exa_client():
    """Dependency to get an initialized Exa client."""
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="EXA_API_KEY environment variable not set."
        )
    try:
        return Exa(api_key=api_key)
    except Exception as e:
        # Catch potential errors during client instantiation
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize Exa client: {e}"
        )

# --- API Endpoint ---

@router.post(
    "/exa-service",
    response_model=ExaContentsResponse,
    summary="Proxy for Exa /contents API",
    description="Receives a URL, calls the Exa /contents API securely, and returns the result.",
    tags=["Exa"]
)
async def get_exa_contents(
    request_body: ExaRequest = Body(...),
    exa: Exa = Depends(get_exa_client)
):
    """
    Acts as a proxy to the Exa API's /contents endpoint.

    - **request_body**: JSON body containing the 'url' to analyze.
    """
    try:
        # Call the synchronous Exa API get_contents method in a threadpool
        response_obj = await run_in_threadpool(
            exa.get_contents, # The function to call
            [str(request_body.url)], # Positional arguments for the function
            text=True # Keyword arguments for the function
        )

        # --- Debugging: Log the response --- 
        print(f"Exa API response object: {response_obj}")
        print(f"Type of Exa response: {type(response_obj)}")
        if isinstance(response_obj, dict):
            print(f"Exa response keys: {response_obj.keys()}")
        elif hasattr(response_obj, '__dict__'):
            print(f"Exa response attributes: {vars(response_obj)}")
        # --- End Debugging ---

        results_list = None
        request_id = None
        cost_dollars = None
        data_container = None

        # Attempt to access the 'data' container first
        if hasattr(response_obj, 'data'):
            data_container = response_obj.data
        elif isinstance(response_obj, dict) and 'data' in response_obj:
            data_container = response_obj.get('data')

        # If 'data' container found, try to access 'results' within it
        if data_container:
            if hasattr(data_container, 'results'):
                results_list = data_container.results
                request_id = getattr(data_container, 'requestId', None)
                cost_dollars = getattr(data_container, 'costDollars', None)
            elif isinstance(data_container, dict) and 'results' in data_container:
                 results_list = data_container.get('results')
                 request_id = data_container.get('requestId')
                 cost_dollars = data_container.get('costDollars')

        # Fallback: Check if response_obj directly has results (less likely based on sample)
        elif hasattr(response_obj, 'results'):
             results_list = response_obj.results
             # requestId/costDollars likely not available here

        # Now process the results_list if found and not empty
        if results_list:
            formatted_results = []
            for res_item in results_list:
                try:
                    if hasattr(res_item, '__dict__'):
                        # If item is an object, convert to dict for Pydantic model
                        item_data = vars(res_item)
                    elif isinstance(res_item, dict):
                        # If item is already a dict
                        item_data = res_item
                    else:
                        print(f"Warning: Unexpected item type in results list: {type(res_item)}")
                        continue # Skip this item
                    
                    # Create Pydantic model instance
                    formatted_results.append(ExaContentResult(**item_data))
                except Exception as item_error:
                    # Log error processing a specific item but continue with others
                    print(f"Warning: Failed to process result item: {res_item}. Error: {item_error}")
                    continue

            # If after processing, we have no valid results (e.g., all items failed parsing)
            if not formatted_results:
                 print("Found results list, but failed to format any items.")
                 raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to process results returned by Exa API."
                )

            # Construct the response data Pydantic model
            response_data = ExaContentsResponseData(
                results=formatted_results,
                requestId=request_id,
                costDollars=cost_dollars
            )
            # Wrap it in the final response model
            return ExaContentsResponse(data=response_data)
        else:
            # Handle cases where results_list is None or empty after checks
            print("Could not find 'results' list in the expected structure or it was empty.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No content found by Exa for the provided URL or API response structure mismatch."
            )

    except Exception as e:
        # Log the error server-side
        print(f"Error calling Exa API or processing response: {e}")
        # Consider logging the traceback for more detail
        import traceback
        traceback.print_exc()

        # Return a generic server error
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve/process content from Exa API: {e}"
        ) 