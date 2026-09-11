from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate
from app.repositories.user import user_repository
from app.core.security import verify_password


class AuthService:
    """
    Handles authentication-specific workflows like registrations and credentials validation.
    """
    
    async def register_user(self, db: AsyncSession, user_in: UserCreate) -> User:
        """
        Validate duplicate emails and register a new user in the system.
        """
        existing_user = await user_repository.get_by_email(db, email=user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists in the system."
            )
        
        return await user_repository.create(db, obj_in=user_in)

    async def authenticate_user(
        self, 
        db: AsyncSession, 
        email: str, 
        password: str
    ) -> Optional[User]:
        """
        Verify input email and password matching with DB.
        Returns the User model if authenticated, None otherwise.
        """
        user = await user_repository.get_by_email(db, email=email)
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
            
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is currently disabled."
            )
            
        return user


# Singleton service instance
auth_service = AuthService()
