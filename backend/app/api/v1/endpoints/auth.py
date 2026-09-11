from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas.user import UserCreate, UserOut
from app.schemas.token import Token
from app.services.auth import auth_service
from app.auth.jwt import create_access_token
from app.core.config import settings
from app.models.user import User

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Register a new user in the platform. Defaults to 'student' role.
    """
    return await auth_service.register_user(db, user_in=user_in)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Standard OAuth2 password flow login. Yields bearer JWT access token.
    Can be used by Swagger OAuth2 helper.
    """
    user = await auth_service.authenticate_user(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email,
        role=user.role,
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserOut)
async def get_my_profile(
    current_user: User = Depends(deps.get_current_user)
):
    """
    Retrieve details of currently logged-in user context.
    """
    return current_user
