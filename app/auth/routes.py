from fastapi import APIRouter, HTTPException, status
from ..dependencies import supabase
from ..schemas import UserCreate, UserLogin, Token
from gotrue.errors import AuthApiError

router = APIRouter()

@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    try:
        # Create user with Supabase auth
        response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password,
            "options": {
                "data": {
                    "name": user.name
                }
            }
        })
        
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed"
            )

        # Return token if registration successful
        return {
            "access_token": response.session.access_token,
            "token_type": "bearer",
            "first_name": user.name.split()[0] if user.name else ""
        }
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.message)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@router.post("/login", response_model=Token)
async def login(user: UserLogin):
    try:
        # Attempt login
        response = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })

        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Get user's first name from metadata
        user_metadata = response.user.user_metadata or {}
        first_name = user_metadata.get("name", "").split()[0] if user_metadata.get("name") else ""

        return {
            "access_token": response.session.access_token,
            "token_type": "bearer",
            "first_name": first_name
        }
    except AuthApiError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e.message)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@router.post("/logout")
async def logout():
    try:
        supabase.auth.sign_out()
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )