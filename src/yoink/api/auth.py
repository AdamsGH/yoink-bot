"""JWT utilities for the Yoink API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt

ALGORITHM = "HS256"


def create_access_token(
    user_id: int,
    role: str,
    secret: str,
    expires_minutes: int,
    first_name: str | None = None,
    username: str | None = None,
) -> str:
    """Create signed JWT."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload: dict = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    if first_name:
        payload["first_name"] = first_name
    if username:
        payload["username"] = username
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def verify_token(token: str, secret: str) -> dict:
    """Decode and verify JWT. Returns payload dict or raises HTTPException 401."""
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
