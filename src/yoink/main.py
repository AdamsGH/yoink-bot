"""
Entry point.
"""
from __future__ import annotations

import asyncio
import logging
import signal

from telegram import Update
from telegram.ext import Application, ContextTypes

from yoink.bot.app import create_app
from yoink.bot.bot_commands import set_default_commands
from yoink.commands import register_all
from yoink.config.settings import Settings
from yoink.storage.db import init_engine, create_tables, get_session_factory
from yoink.services.cookies import CookieManager
from yoink.services.nsfw import NsfwChecker
from yoink.storage.download_log import DownloadLogRepo
from yoink.storage.file_cache import FileCacheRepo
from yoink.storage.group_repo import GroupRepo
from yoink.storage.user_settings import UserSettingsRepo
from yoink.storage.bot_settings import BotSettingsRepo

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def _error_handler(update: object, context: "ContextTypes.DEFAULT_TYPE") -> None:  # type: ignore[name-defined]
    logger.warning("PTB error: %s", context.error)


async def _evict_cache_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    cache: FileCacheRepo | None = context.bot_data.get("file_cache")
    if cache:
        n = await cache.evict_expired()
        if n:
            logger.info("Evicted %d expired file cache entries", n)


async def post_init(app: Application) -> None:
    settings: Settings = app.bot_data["settings"]
    init_engine(settings.database_url, echo=settings.database_echo)
    await create_tables()
    session_factory = get_session_factory()

    app.bot_data["file_cache"] = FileCacheRepo(session_factory)
    app.bot_data["download_log"] = DownloadLogRepo(session_factory)
    app.bot_data["cookie_manager"] = CookieManager(session_factory)
    app.bot_data["group_repo"] = GroupRepo(session_factory)
    bot_settings_repo = BotSettingsRepo(session_factory)
    app.bot_data["bot_settings_repo"] = bot_settings_repo
    app.bot_data["user_repo"] = UserSettingsRepo(session_factory, owner_id=settings.owner_id)

    nsfw_checker = NsfwChecker(session_factory)
    await nsfw_checker.load()
    app.bot_data["nsfw_checker"] = nsfw_checker
    from yoink.bot.progress import setup_job
    setup_job(app)
    app.job_queue.run_repeating(_evict_cache_job, interval=86400, first=3600, name="evict_cache")
    # Local Bot API server ignores drop_pending_updates in deleteWebhook for polling mode.
    # Drain manually: getUpdates with offset=-1 returns the latest update_id,
    # then getUpdates with offset=latest+1 marks everything as read.
    try:
        updates = await app.bot.get_updates(offset=-1, limit=1, timeout=0)
        if updates:
            await app.bot.get_updates(offset=updates[-1].update_id + 1, limit=1, timeout=0)
            logger.info("Drained pending updates (last id=%d)", updates[-1].update_id)
    except Exception as e:
        logger.warning("Could not drain pending updates: %s", e)

    me = await app.bot.get_me()
    await set_default_commands(app.bot)
    logger.info("Bot started  - @%s", me.username)


async def post_shutdown(app: Application) -> None:
    logger.info("Shutdown complete")


def main() -> None:
    settings = Settings()

    app = create_app(settings)
    app.bot_data["settings"] = settings

    app.post_init = post_init
    app.post_shutdown = post_shutdown

    register_all(app)
    app.add_error_handler(_error_handler)

    logger.info("Starting polling…")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        bootstrap_retries=-1,
        poll_interval=0.5,
        timeout=10,
    )
