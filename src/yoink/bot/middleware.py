"""
Cross-cutting handler utilities.

PTB doesn't have middleware in the Pyrogram sense - we use
TypedDict on context.bot_data and helper functions instead.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from sqlalchemy.ext.asyncio import async_sessionmaker

from yoink.config.settings import Settings
from yoink.storage.user_settings import UserSettingsRepo

logger = logging.getLogger(__name__)


def get_session_factory(context: ContextTypes.DEFAULT_TYPE) -> async_sessionmaker:
    return context.bot_data["session_factory"]


def get_settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.bot_data["settings"]


def get_user_repo(context: ContextTypes.DEFAULT_TYPE) -> UserSettingsRepo:
    return context.bot_data["user_repo"]


async def is_blocked(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    repo = get_user_repo(context)
    return await repo.is_blocked(user_id)


async def guard_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if user is the owner, reply with error and return False otherwise."""
    settings = get_settings(context)
    user = update.effective_user
    if user and user.id == settings.owner_id:
        return True
    if update.message:
        await update.message.reply_text("Not authorized.")
    return False
