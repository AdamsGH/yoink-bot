"""
Telegram BotCommand registration helpers.

Scopes:
- BotCommandScopeDefault           - private chats, full list shown before /start
- BotCommandScopeAllGroupChats     - groups: only download commands (no settings noise)
- BotCommandScopeChat              - per-user personalised list set on /start (private only)
"""
from __future__ import annotations

import logging

from telegram import Bot, BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeChat, BotCommandScopeDefault
from telegram.error import TelegramError

from yoink.storage.models import UserRole

logger = logging.getLogger(__name__)

_BASE_COMMANDS: list[tuple[str, str]] = [
    ("start",       "Welcome"),
    ("help",        "Show help"),
    ("settings",    "Your preferences"),
    ("format",      "Video format / quality"),
    ("lang",        "Interface language"),
    ("proxy",       "Toggle proxy"),
    ("split",       "Set split size"),
    ("subs",        "Subtitles"),
    ("args",        "Custom yt-dlp args"),
    ("nsfw",        "NSFW blur toggle"),
    ("mediainfo",   "Mediainfo toggle"),
    ("video",       "Download video: /video <url>"),
    ("audio",       "Download audio: /audio <url>"),
    ("image",       "Download images: /image <url>"),
    ("list",        "List available formats"),
    ("link",        "Get direct link"),
    ("playlist",    "Playlist mode"),
    ("cut",         "Cut a clip from video"),
    ("search",      "Search"),
    ("tags",        "Tags"),
    ("clean",       "Clean your data"),
    ("keyboard",    "Keyboard layout"),
    ("cookie",      "Manage cookies"),
]

# Commands shown in groups  - only those that make sense without a private context
_GROUP_COMMANDS: list[tuple[str, str]] = [
    ("video",   "Download video: /video <url>"),
    ("audio",   "Download audio: /audio <url>"),
    ("image",   "Download images: /image <url>"),
    ("cut",     "Cut a clip: /cut <url> <start> <end>"),
    ("search",  "Search: /search <query>"),
    ("link",    "Get direct link: /link <url>"),
    ("playlist","Download playlist: /playlist <url>"),
]

_MOD_COMMANDS: list[tuple[str, str]] = [
    ("get_log",     "Get user download log"),
    ("usage",       "User usage stats"),
]

_ADMIN_COMMANDS: list[tuple[str, str]] = [
    ("block",        "Block a user"),
    ("unblock",      "Unblock a user"),
    ("ban_time",     "Temporary ban"),
    ("broadcast",    "Broadcast a message"),
    ("uncache",      "Remove URL from cache"),
    ("reload_cache", "Reload file cache"),
    ("group",        "Group access control"),
    ("thread",       "Thread access control"),
]

_OWNER_COMMANDS: list[tuple[str, str]] = [
    ("runtime", "Bot runtime info"),
]


def _commands_for_role(role: UserRole) -> list[BotCommand]:
    if role == UserRole.banned:
        return []

    cmds = list(_BASE_COMMANDS)

    if role in (UserRole.owner, UserRole.admin, UserRole.moderator):
        cmds += _MOD_COMMANDS

    if role in (UserRole.owner, UserRole.admin):
        cmds += _ADMIN_COMMANDS

    if role == UserRole.owner:
        cmds += _OWNER_COMMANDS

    return [BotCommand(command=c, description=d) for c, d in cmds]


async def set_default_commands(bot: Bot) -> None:
    """Set commands for all scopes on startup."""
    try:
        # Private chats: full list
        await bot.set_my_commands(
            commands=[BotCommand(c, d) for c, d in _BASE_COMMANDS],
            scope=BotCommandScopeDefault(),
        )
        logger.info("Default commands set (%d)", len(_BASE_COMMANDS))
    except TelegramError as e:
        logger.warning("Failed to set default commands: %s", e)

    try:
        # Groups: minimal download-only set
        await bot.set_my_commands(
            commands=[BotCommand(c, d) for c, d in _GROUP_COMMANDS],
            scope=BotCommandScopeAllGroupChats(),
        )
        logger.info("Group commands set (%d)", len(_GROUP_COMMANDS))
    except TelegramError as e:
        logger.warning("Failed to set group commands: %s", e)


async def set_user_commands(bot: Bot, chat_id: int, role: UserRole) -> None:
    """Set per-chat commands for a private chat based on user role."""
    commands = _commands_for_role(role)
    try:
        if commands:
            await bot.set_my_commands(
                commands=commands,
                scope=BotCommandScopeChat(chat_id=chat_id),
            )
        else:
            await bot.delete_my_commands(
                scope=BotCommandScopeChat(chat_id=chat_id),
            )
        logger.debug(
            "Commands set for chat %d (role=%s): %d items",
            chat_id, role.value, len(commands),
        )
    except TelegramError as e:
        logger.warning("Failed to set commands for chat %d: %s", chat_id, e)
