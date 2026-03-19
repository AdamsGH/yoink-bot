"""User settings endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.api.deps import get_current_user, get_db, require_role
from yoink.api.schemas import SettingsResponse, SettingsUpdateRequest
from yoink.storage.models import User, UserRole

router = APIRouter(prefix="/settings", tags=["settings"])

_ADMIN_ROLES = (UserRole.owner, UserRole.admin)

_SETTINGS_FIELDS = {
    "language", "quality", "codec", "container", "proxy_enabled", "proxy_url",
    "keyboard", "subs_enabled", "subs_auto", "subs_always_ask", "subs_lang",
    "split_size", "nsfw_blur", "mediainfo", "send_as_file", "theme", "args_json",
}


def _user_to_settings(user: User) -> SettingsResponse:
    return SettingsResponse(
        user_id=user.id,
        language=user.language,
        quality=user.quality,
        codec=user.codec,
        container=user.container,
        proxy_enabled=user.proxy_enabled,
        proxy_url=user.proxy_url,
        keyboard=user.keyboard,
        subs_enabled=user.subs_enabled,
        subs_auto=user.subs_auto,
        subs_always_ask=user.subs_always_ask,
        subs_lang=user.subs_lang,
        split_size=user.split_size,
        nsfw_blur=user.nsfw_blur,
        mediainfo=user.mediainfo,
        send_as_file=user.send_as_file,
        theme=user.theme,
        args_json=user.args_json if user.args_json is not None else {},
    )


async def _apply_settings(user: User, body: SettingsUpdateRequest) -> None:
    data = body.model_dump(exclude_unset=True)
    for field, val in data.items():
        if field in _SETTINGS_FIELDS:
            setattr(user, field, val)
    user.updated_at = datetime.now(timezone.utc)


@router.get("", response_model=SettingsResponse)
async def get_my_settings(
    current_user: User = Depends(get_current_user),
) -> SettingsResponse:
    """Get the authenticated user's settings."""
    return _user_to_settings(current_user)


@router.patch("", response_model=SettingsResponse)
async def update_my_settings(
    body: SettingsUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SettingsResponse:
    """Update the authenticated user's settings."""
    user = await session.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await _apply_settings(user, body)
    await session.commit()
    await session.refresh(user)
    return _user_to_settings(user)


@router.get("/{user_id}", response_model=SettingsResponse)
async def get_user_settings(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> SettingsResponse:
    """Get a specific user's settings (admin+)."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_to_settings(user)


@router.patch("/{user_id}", response_model=SettingsResponse)
async def update_user_settings(
    user_id: int,
    body: SettingsUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> SettingsResponse:
    """Update a specific user's settings (admin+)."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await _apply_settings(user, body)
    await session.commit()
    await session.refresh(user)
    return _user_to_settings(user)
