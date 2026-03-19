"""Download log - records every completed or failed download."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import async_sessionmaker

from yoink.storage.models import DownloadLog as DownloadLogModel, User

logger = logging.getLogger(__name__)


class DownloadLogRepo:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._factory = session_factory

    async def write(
        self,
        user_id: int,
        url: str,
        *,
        title: str | None = None,
        quality: str | None = None,
        file_size: int | None = None,
        duration: float | None = None,
        status: str = "ok",
        error_msg: str | None = None,
        group_id: int | None = None,
        thread_id: int | None = None,
        message_id: int | None = None,
        clip_start: int | None = None,
        clip_end: int | None = None,
    ) -> None:
        domain = urlparse(url).netloc or None
        try:
            async with self._factory() as session:
                # Ensure user row exists (download_log has FK to users)
                user = await session.get(User, user_id)
                if user is None:
                    user = User(id=user_id)
                    session.add(user)
                    await session.flush()
                entry = DownloadLogModel(
                    user_id=user_id,
                    url=url,
                    domain=domain,
                    title=title,
                    quality=quality,
                    file_size=file_size,
                    duration=duration,
                    status=status,
                    error_msg=error_msg,
                    group_id=group_id,
                    thread_id=thread_id,
                    message_id=message_id,
                    clip_start=clip_start,
                    clip_end=clip_end,
                )
                session.add(entry)
                await session.commit()
        except Exception as e:
            logger.warning("Failed to write download_log: %s", e)
