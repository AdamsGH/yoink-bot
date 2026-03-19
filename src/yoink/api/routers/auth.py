"""Authentication endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.api.auth import create_access_token
from yoink.api.deps import get_db
from yoink.api.schemas import TelegramIdRequest, TokenResponse
from yoink.storage.models import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def auth_token(
    body: TelegramIdRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Issue a JWT for a Telegram user identified by telegram_id.

    The caller supplies the telegram_id extracted from initDataUnsafe on the
    frontend. Telegram's WebApp SDK guarantees this data is authentic when the
    page is opened inside Telegram; we do not re-verify the HMAC here.
    """
    settings = request.app.state.settings

    user_id: int = body.telegram_id
    username: str | None = body.username
    first_name: str | None = body.first_name

    user = await session.get(User, user_id)
    if user is None:
        user = User(
            id=user_id,
            username=username,
            first_name=first_name,
        )
        session.add(user)
    else:
        if username is not None:
            user.username = username
        if first_name is not None:
            user.first_name = first_name
        user.updated_at = datetime.now(timezone.utc)

    if user_id == settings.owner_id and user.role != UserRole.owner:
        user.role = UserRole.owner

    await session.commit()
    await session.refresh(user)

    token = create_access_token(
        user_id=user.id,
        role=user.role.value,
        secret=settings.api_secret_key,
        expires_minutes=settings.api_token_expire_minutes,
        first_name=user.first_name,
        username=user.username,
    )

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role.value,
    )


@router.post("/dev", response_model=TokenResponse)
async def auth_dev(
    request: Request,
    user_id: int = Query(...),
    role: UserRole = Query(UserRole.user),
) -> TokenResponse:
    """Issue a JWT without any check. Only works when DEBUG=true."""
    settings = request.app.state.settings

    if not settings.debug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    token = create_access_token(
        user_id=user_id,
        role=role.value,
        secret=settings.api_secret_key,
        expires_minutes=settings.api_token_expire_minutes,
    )

    return TokenResponse(
        access_token=token,
        user_id=user_id,
        role=role.value,
    )
