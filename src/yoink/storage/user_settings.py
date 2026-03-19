"""Per-user settings CRUD. Single source of truth - no .txt files."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from yoink.storage.models import BotSetting, User, UserRole


@dataclass
class UserSettings:
    user_id: int
    role: UserRole = UserRole.user
    language: str = "en"
    quality: str = "best"
    codec: str = "avc1"
    container: str = "mp4"
    proxy_enabled: bool = False
    proxy_url: str | None = None
    keyboard: str = "2x3"
    subs_enabled: bool = False
    subs_auto: bool = False
    subs_always_ask: bool = False
    subs_lang: str = "en"
    split_size: int = 2_043_000_000
    nsfw_blur: bool = True
    mediainfo: bool = False
    send_as_file: bool = False
    args_json: dict[str, Any] = field(default_factory=dict)
    blocked: bool = False
    ban_until: datetime | None = None


def _user_to_settings(user: User) -> UserSettings:
    now = datetime.now(timezone.utc)
    ban_until = user.ban_until
    # Ensure ban_until is timezone-aware for comparison
    if ban_until is not None and ban_until.tzinfo is None:
        ban_until = ban_until.replace(tzinfo=timezone.utc)
    blocked = (
        user.role in (UserRole.banned, UserRole.restricted)
        or (ban_until is not None and ban_until > now)
    )
    return UserSettings(
        user_id=user.id,
        role=user.role,
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
        args_json=user.args_json if user.args_json is not None else {},
        blocked=blocked,
        ban_until=ban_until,
    )


# Fields that are valid to set directly on the User ORM model
_USER_FIELDS = {
    "language", "quality", "codec", "container", "proxy_enabled", "keyboard",
    "subs_enabled", "subs_auto", "subs_always_ask", "subs_lang",
    "split_size", "nsfw_blur", "mediainfo", "send_as_file", "args_json",
    "ban_until", "role",
}

# Map legacy "blocked" kwarg to role
_BLOCKED_ROLE = UserRole.banned
_UNBLOCKED_ROLE = UserRole.user


class UserSettingsRepo:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        owner_id: int | None = None,
    ) -> None:
        self._factory = session_factory
        self._owner_id = owner_id

    async def _default_role(self, session: AsyncSession) -> UserRole:
        """Read bot_access_mode from DB to determine role for new users."""
        row = await session.get(BotSetting, "bot_access_mode")
        if row and row.value == "approved_only":
            return UserRole.restricted
        return UserRole.user

    async def get_or_create(self, user_id: int) -> UserSettings:
        """Return settings for user, creating defaults if not exists.

        New users whose ID matches owner_id get UserRole.owner on first insert.
        All other new users get UserRole.user (open mode) or UserRole.restricted
        (approved_only mode), read live from bot_access_mode setting.
        """
        async with self._factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                if self._owner_id and user_id == self._owner_id:
                    role = UserRole.owner
                else:
                    role = await self._default_role(session)
                user = User(id=user_id, role=role)
                session.add(user)
                await session.commit()
                await session.refresh(user)
            return _user_to_settings(user)

    # Keep `get` as alias for backwards compatibility
    async def get(self, user_id: int) -> UserSettings:
        return await self.get_or_create(user_id)

    async def update(self, user_id: int, **kwargs: Any) -> UserSettings:
        """Update one or more fields for a user."""
        async with self._factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                user = User(id=user_id)
                session.add(user)

            # Handle legacy "blocked" bool kwarg - map to role
            if "blocked" in kwargs:
                blocked_val = kwargs.pop("blocked")
                if blocked_val:
                    kwargs.setdefault("role", _BLOCKED_ROLE)
                else:
                    # Only unblock if currently banned; don't overwrite other roles
                    if user.role == UserRole.banned:
                        kwargs.setdefault("role", _UNBLOCKED_ROLE)
                    # Also clear ban_until when unblocking
                    kwargs.setdefault("ban_until", None)

            for key, val in kwargs.items():
                if key in _USER_FIELDS:
                    setattr(user, key, val)

            user.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(user)
            return _user_to_settings(user)

    async def set_language(self, user_id: int, lang: str) -> None:
        await self.update(user_id, language=lang)

    async def set_quality(self, user_id: int, quality: str) -> None:
        await self.update(user_id, quality=quality)

    async def toggle_proxy(self, user_id: int, enabled: bool) -> None:
        await self.update(user_id, proxy_enabled=enabled)

    async def set_args(self, user_id: int, args: dict[str, Any]) -> None:
        await self.update(user_id, args_json=args)

    async def is_blocked(self, user_id: int) -> bool:
        async with self._factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                return False
            now = datetime.now(timezone.utc)
            if user.role in (UserRole.banned, UserRole.restricted):
                return True
            if user.ban_until is not None:
                ban_until = user.ban_until
                if ban_until.tzinfo is None:
                    ban_until = ban_until.replace(tzinfo=timezone.utc)
                if ban_until > now:
                    return True
                # Ban expired - clear it
                await self.update(user_id, ban_until=None)
            return False
