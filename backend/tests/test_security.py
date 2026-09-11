from datetime import timedelta
from jose import jwt

from app.core.security import get_password_hash, verify_password
from app.auth.jwt import create_access_token, ALGORITHM
from app.core.config import settings


def test_password_hashing():
    """Verify password hashing creates unique values and evaluates accurately."""
    password = "sppu_student_pass_2026"
    hashed = get_password_hash(password)
    
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_generation():
    """Verify JWT access tokens can be signed and contain expected subject claims."""
    email = "student@sppu.edu.in"
    role = "student"
    
    token = create_access_token(
        subject=email,
        role=role,
        expires_delta=timedelta(minutes=15)
    )
    
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Decode token to verify contents
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload.get("sub") == email
    assert payload.get("role") == role
    assert "exp" in payload
