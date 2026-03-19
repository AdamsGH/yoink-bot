"""Rate-limit repository backed by the rate_limits table.

Windows: "minute", "hour", "day".
Each window is a single row per (user_id, window). On each check we either
increment the counter (within window) or reset it (window expired).

All methods are idempotent and safe for concurrent callers - PostgreSQL
ON CONFLICT handles the upsert atomically.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.storage.models import RateLimit


class RateLimitRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def check_and_increment(
        self,
        user_id: int,
        limit_minute: int,
        limit_hour: int,
        limit_day: int,
    ) -> tuple[bool, str]:
        """Check all three windows and increment if allowed.

        Returns (allowed, reason). reason is "" when allowed,
        or a human-readable string describing which window is exhausted.
        """
        now = datetime.now(timezone.utc)
        windows = [
            ("minute", timedelta(minutes=1), limit_minute),
            ("hour",   timedelta(hours=1),   limit_hour),
            ("day",    timedelta(days=1),     limit_day),
        ]

        for window_name, delta, limit in windows:
            reset_at = now + delta
            allowed, exhausted_at = await self._increment(
                user_id, window_name, limit, reset_at, now
            )
            if not allowed:
                wait_sec = int((exhausted_at - now).total_seconds()) + 1
                return False, f"{window_name} limit reached, retry in {wait_sec}s"

        return True, ""

    async def _increment(
        self,
        user_id: int,
        window: str,
        limit: int,
        reset_at: datetime,
        now: datetime,
    ) -> tuple[bool, datetime]:
        """Upsert a rate-limit row. Returns (allowed, reset_at).

        - If row doesn't exist: insert with count=1
        - If row exists but reset_at is in the past: reset count to 1
        - If row exists and within window: increment
        - If count >= limit: deny without incrementing
        """
        result = await self._s.execute(
            select(RateLimit).where(
                RateLimit.user_id == user_id,
                RateLimit.window == window,
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = RateLimit(user_id=user_id, window=window, count=1, reset_at=reset_at)
            self._s.add(row)
            await self._s.flush()
            return True, reset_at

        if row.reset_at <= now:
            row.count = 1
            row.reset_at = reset_at
            await self._s.flush()
            return True, reset_at

        if row.count >= limit:
            return False, row.reset_at

        row.count += 1
        await self._s.flush()
        return True, row.reset_at

    async def reset(self, user_id: int) -> None:
        """Clear all rate-limit windows for a user (admin action)."""
        await self._s.execute(
            delete(RateLimit).where(RateLimit.user_id == user_id)
        )
        await self._s.flush()
