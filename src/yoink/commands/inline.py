"""
Inline query handler  - @botname <query> in any chat.

Flow:
  1. User types "@botname cats video" anywhere in Telegram
  2. Bot searches YouTube via yt-dlp ytsearch and returns up to 5 results
     as InlineQueryResultArticle items showing title + channel + duration
  3. User taps a result → the URL is inserted into the chat as a text message
  4. url_handler picks up the URL and starts the normal download pipeline

Requires inline mode enabled via @BotFather (/setinline).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

from telegram import (
    InlineQuery,
    InlineQueryResultCachedVideo,
    InlineQueryResultsButton,
    InlineQueryResultVideo,
    InputTextMessageContent,
    Update,
)
from telegram.ext import Application, ContextTypes, InlineQueryHandler

from yoink.bot.middleware import is_blocked
from yoink.storage.file_cache import FileCacheRepo, make_cache_key

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="inline_search")

_MAX_RESULTS = 8
_MIN_QUERY_LEN = 2
_CACHE_TIME = 30  # seconds Telegram caches results client-side


def _do_search(query: str) -> list[dict]:
    """Blocking yt-dlp YouTube search. Runs in thread pool."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{_MAX_RESULTS}:{query}", download=False)
        if not info:
            return []
        return info.get("entries") or []
    except Exception as e:
        logger.warning("Inline search failed for %r: %s", query, e)
        return []


def _fmt_duration(seconds: int | float | None) -> str:
    if not seconds:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def _best_thumbnail(entry: dict) -> str | None:
    """Pick the largest available thumbnail URL from a flat yt-dlp entry."""
    thumbs = entry.get("thumbnails") or []
    if thumbs:
        # thumbnails are ordered small→large; take the last one
        return thumbs[-1].get("url")
    return entry.get("thumbnail")


def _entry_to_result(entry: dict) -> InlineQueryResultVideo | None:
    """Convert a yt-dlp flat entry to an InlineQueryResultVideo.

    InlineQueryResultVideo with mime_type=text/html renders a rich YouTube
    preview card (title, thumbnail, channel) directly in the results list.
    input_message_content overrides what gets sent to chat  - we send the
    plain URL so url_handler picks it up and starts the download pipeline.
    """
    video_id = entry.get("id") or ""
    url = entry.get("url") or entry.get("webpage_url") or ""
    if not url or not url.startswith(("http://", "https://")):
        return None

    # Normalise to canonical watch URL (flat search returns short form)
    if video_id and "youtube.com" not in url and "youtu.be" not in url:
        url = f"https://www.youtube.com/watch?v={video_id}"

    title = (entry.get("title") or "Unknown")[:120]
    channel = entry.get("channel") or entry.get("uploader") or ""
    duration = _fmt_duration(entry.get("duration"))
    view_count = entry.get("view_count")

    parts: list[str] = []
    if channel:
        parts.append(channel)
    if duration:
        parts.append(duration)
    if view_count:
        if view_count >= 1_000_000:
            parts.append(f"{view_count / 1_000_000:.1f}M views")
        elif view_count >= 1_000:
            parts.append(f"{view_count // 1_000}K views")
        else:
            parts.append(f"{view_count} views")
    description = " · ".join(parts) if parts else ""

    thumbnail_url = _best_thumbnail(entry)

    # Stable ID from video URL for client-side dedup
    result_id = hashlib.md5(url.encode()).hexdigest()[:16]

    return InlineQueryResultVideo(
        id=result_id,
        title=title,
        description=description,
        # mime_type=text/html + YouTube URL → Telegram renders oEmbed preview card
        video_url=url,
        mime_type="text/html",
        thumbnail_url=thumbnail_url or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        # What actually gets inserted into chat when user taps
        input_message_content=InputTextMessageContent(url),
    )


async def _handle_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    inline_query: InlineQuery | None = update.inline_query
    if not inline_query:
        return

    user = inline_query.from_user
    if user and await is_blocked(user.id, context):
        await inline_query.answer([], cache_time=0)
        return

    query = (inline_query.query or "").strip()

    if len(query) < _MIN_QUERY_LEN:
        await inline_query.answer(
            [],
            cache_time=0,
            button=InlineQueryResultsButton(
                text="Type at least 2 characters to search",
                start_parameter="search_help",
            ),
        )
        return

    # Check if query looks like a URL  - serve from file cache if available
    if query.startswith(("http://", "https://")):
        file_cache: FileCacheRepo | None = context.bot_data.get("file_cache")
        if file_cache:
            cache_key = make_cache_key(query)
            cached = await file_cache.get(cache_key) if cache_key else None
            if cached and cached.file_type == "video":
                result_id = hashlib.md5(query.encode()).hexdigest()[:16]
                await inline_query.answer(
                    [InlineQueryResultCachedVideo(
                        id=result_id,
                        video_file_id=cached.file_id,
                        title=cached.title or query,
                    )],
                    cache_time=300,
                )
                return

    loop = asyncio.get_running_loop()
    entries = await loop.run_in_executor(_executor, _do_search, query)

    results: list[InlineQueryResultVideo] = []
    for entry in entries:
        item = _entry_to_result(entry)
        if item:
            results.append(item)

    if not results:
        await inline_query.answer(
            [],
            cache_time=_CACHE_TIME,
            button=InlineQueryResultsButton(
                text="No results found",
                start_parameter="search_help",
            ),
        )
        return

    await inline_query.answer(results, cache_time=_CACHE_TIME)


def register(app: Application) -> None:
    app.add_handler(InlineQueryHandler(_handle_inline))
