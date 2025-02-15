from fastapi import APIRouter, HTTPException, Depends
from supabase import Client, create_client
from app.schemas import UserCreate, UserLogin, Token
import os
from typing import Optional
from fastapi.security import OAuth2PasswordBearer

router = APIRouter()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.post("/login")
async def login(user_data: UserLogin):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user_data.email,
            "password": user_data.password
        })
        
        if hasattr(response, 'error') and response.error is not None:
            raise HTTPException(status_code=401, detail=str(response.error.message))
            
        return {
            "access_token": response.session.access_token,
            "token_type": "bearer",
            "user": response.user
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.post("/register")
async def register(user_data: UserCreate):
    try:
        response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "name": user_data.name
                }
            }
        })
        
        if hasattr(response, 'error') and response.error is not None:
            raise HTTPException(status_code=400, detail=str(response.error.message))
            
        return {
            "message": "Registration successful. Please check your email for verification.",
            "user": response.user
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    try:
        response = supabase.auth.sign_out()
        if hasattr(response, 'error') and response.error is not None:
            raise HTTPException(status_code=400, detail=str(response.error.message))
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))