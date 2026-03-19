"""Global bot settings stored in DB, editable via Admin UI."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from yoink.storage.models import BotSetting, UserRole

# Known keys with their types and defaults
DEFAULTS: dict[str, Any] = {
    # Minimum role to use shared browser profile cookies
    "browser_cookies_min_role": UserRole.owner.value,
    # Private chat access: "open" = anyone, "approved_only" = role must be >= user
    # (new users get 'restricted' in approved_only mode instead of 'user')
    "bot_access_mode": "open",
}


class BotSettingsRepo:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._factory = session_factory

    async def get(self, key: str) -> str | None:
        async with self._factory() as session:
            row = await session.get(BotSetting, key)
            return row.value if row else None

    async def set(self, key: str, value: str) -> None:
        async with self._factory() as session:
            row = await session.get(BotSetting, key)
            if row is None:
                session.add(BotSetting(key=key, value=value))
            else:
                row.value = value
            await session.commit()

    async def get_all(self) -> dict[str, str | None]:
        async with self._factory() as session:
            rows = (await session.execute(select(BotSetting))).scalars().all()
            result = dict(DEFAULTS)
            for row in rows:
                result[row.key] = row.value
            return result

    async def get_browser_cookies_min_role(self) -> UserRole:
        val = await self.get("browser_cookies_min_role")
        if val is None:
            return UserRole.owner
        try:
            return UserRole(val)
        except ValueError:
            return UserRole.owner

    async def get_bot_access_mode(self) -> str:
        """Return 'open' or 'approved_only'."""
        val = await self.get("bot_access_mode")
        return val if val in ("open", "approved_only") else "open"
