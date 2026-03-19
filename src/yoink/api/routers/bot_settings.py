"""Bot-wide settings endpoints (owner/admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.api.deps import get_db, require_role
from yoink.storage.models import BotSetting, User, UserRole
from yoink.storage.bot_settings import DEFAULTS

router = APIRouter(prefix="/bot-settings", tags=["bot-settings"])

_ADMIN = (UserRole.owner, UserRole.admin)


class BotSettingsResponse(BaseModel):
    settings: dict[str, str | None]


class BotSettingUpdate(BaseModel):
    value: str | None


@router.get("", response_model=BotSettingsResponse)
async def get_bot_settings(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*_ADMIN)),
) -> BotSettingsResponse:
    rows = (await session.execute(select(BotSetting))).scalars().all()
    result: dict[str, str | None] = dict(DEFAULTS)
    for row in rows:
        result[row.key] = row.value
    return BotSettingsResponse(settings=result)


@router.patch("/{key}", response_model=BotSettingsResponse)
async def update_bot_setting(
    key: str,
    body: BotSettingUpdate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*_ADMIN)),
) -> BotSettingsResponse:
    if key not in DEFAULTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown key: {key}")

    row = await session.get(BotSetting, key)
    if row is None:
        session.add(BotSetting(key=key, value=body.value))
    else:
        row.value = body.value
    await session.commit()

    rows = (await session.execute(select(BotSetting))).scalars().all()
    result: dict[str, str | None] = dict(DEFAULTS)
    for row in rows:
        result[row.key] = row.value
    return BotSettingsResponse(settings=result)
