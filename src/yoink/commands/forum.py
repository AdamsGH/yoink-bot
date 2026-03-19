"""
Forum topic discovery handler.

Telegram does not expose a "list topics" API. The only way to learn topic
names is to observe the service messages Telegram sends when a topic is
created or renamed. We persist them so the admin UI can show named topics
in the thread-policy selector instead of raw IDs.

Handled service message types:
  - forum_topic_created  (new topic)
  - forum_topic_edited   (renamed topic)
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from yoink.storage.group_repo import GroupRepo

logger = logging.getLogger(__name__)


def _get_group_repo(context: ContextTypes.DEFAULT_TYPE) -> GroupRepo | None:
    return context.bot_data.get("group_repo")


async def _handle_topic_created(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.forum_topic_created or not msg.message_thread_id:
        return
    chat = update.effective_chat
    if not chat:
        return

    group_repo = _get_group_repo(context)
    if group_repo is None:
        return

    thread_id = msg.message_thread_id
    name = msg.forum_topic_created.name
    logger.info("Forum topic created: group=%d thread=%d name=%r", chat.id, thread_id, name)

    await group_repo.upsert(group_id=chat.id, title=chat.title)
    await group_repo.upsert_thread_name(chat.id, thread_id, name)


async def _handle_topic_edited(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.forum_topic_edited or not msg.message_thread_id:
        return
    chat = update.effective_chat
    if not chat:
        return

    edited = msg.forum_topic_edited
    if not edited.name:
        return

    group_repo = _get_group_repo(context)
    if group_repo is None:
        return

    thread_id = msg.message_thread_id
    name = edited.name
    logger.info("Forum topic renamed: group=%d thread=%d name=%r", chat.id, thread_id, name)

    await group_repo.upsert_thread_name(chat.id, thread_id, name)


def register(app: Application) -> None:
    # forum_topic_created is a service message  - it has no text and is not a command
    app.add_handler(MessageHandler(
        filters.StatusUpdate.FORUM_TOPIC_CREATED,
        _handle_topic_created,
    ))
    app.add_handler(MessageHandler(
        filters.StatusUpdate.FORUM_TOPIC_EDITED,
        _handle_topic_edited,
    ))
