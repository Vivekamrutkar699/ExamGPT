import bcrypt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare a plain text password with its encrypted hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Create a secure bcrypt hash of a plain text password."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

