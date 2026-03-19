"""FastAPI dependency injection."""
from __future__ import annotations

from collections.abc import AsyncGenerator, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.api.auth import verify_token
from yoink.storage.models import User, UserRole

bearer = HTTPBearer()


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession from the app-level session_factory."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Verify JWT, load user from DB, raise 401 if invalid."""
    settings = request.app.state.settings
    payload = verify_token(credentials.credentials, settings.api_secret_key)

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await session.get(User, int(user_id_str))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*roles: UserRole) -> Callable:
    """Return a FastAPI dependency that checks the current user's role."""
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user.role!r} is not permitted; required: {[r.value for r in roles]}",
            )
        return user
    return _check
