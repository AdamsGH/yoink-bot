"""File ID cache - avoid re-uploading files already sent to Telegram."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from yoink.storage.models import FileCache as FileCacheModel

logger = logging.getLogger(__name__)

TTL_DAYS = 30


@dataclass
class CachedFile:
    cache_key: str
    file_id: str
    file_type: str       # "video" | "document" | "audio"
    title: str | None
    duration: float | None
    width: int | None
    height: int | None
    file_size: int | None


def make_cache_key(url: str, start_sec: int | None = None, end_sec: int | None = None) -> str:
    """Stable cache key from a normalized URL and optional clip range."""
    key = url
    if start_sec is not None and end_sec is not None:
        key = f"{url}@{start_sec}-{end_sec}"
    return hashlib.sha256(key.encode()).hexdigest()


class FileCacheRepo:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._factory = session_factory

    async def get(self, cache_key: str) -> CachedFile | None:
        now = datetime.now(timezone.utc)
        async with self._factory() as session:
            row = await session.get(FileCacheModel, cache_key)
            if row is None:
                return None
            expires = row.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= now:
                return None
            return CachedFile(
                cache_key=row.cache_key,
                file_id=row.file_id,
                file_type=row.file_type,
                title=row.title,
                duration=row.duration,
                width=row.width,
                height=row.height,
                file_size=row.file_size,
            )

    async def store(self, entry: CachedFile) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=TTL_DAYS)
        async with self._factory() as session:
            row = await session.get(FileCacheModel, entry.cache_key)
            if row is None:
                row = FileCacheModel(cache_key=entry.cache_key)
                session.add(row)
            row.file_id = entry.file_id
            row.file_type = entry.file_type
            row.title = entry.title
            row.duration = entry.duration
            row.width = entry.width
            row.height = entry.height
            row.file_size = entry.file_size
            row.expires_at = expires_at
            await session.commit()
        logger.debug("Cached file_id for key %s", entry.cache_key)

    async def delete(self, cache_key: str) -> bool:
        """Remove a specific cache entry. Returns True if something was deleted."""
        async with self._factory() as session:
            result = await session.execute(
                delete(FileCacheModel).where(FileCacheModel.cache_key == cache_key)
            )
            await session.commit()
            return result.rowcount > 0

    async def evict_expired(self) -> int:
        now = datetime.now(timezone.utc)
        async with self._factory() as session:
            result = await session.execute(
                delete(FileCacheModel).where(FileCacheModel.expires_at <= now)
            )
            await session.commit()
            return result.rowcount
