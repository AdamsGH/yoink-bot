"""
/start and /help commands.

In groups: silently ignored  - settings and onboarding belong in private chat.
In private: full welcome + personalised command list.
"""
from __future__ import annotations

import logging

from telegram import LinkPreviewOptions, Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from yoink.bot.bot_commands import set_user_commands
from yoink.bot.middleware import get_user_repo
from yoink.storage.models import UserRole

logger = logging.getLogger(__name__)


async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    user_repo = get_user_repo(context)
    user_id = update.effective_user.id
    user_settings = await user_repo.get_or_create(user_id)

    await set_user_commands(context.bot, update.message.chat_id, user_settings.role)

    if user_settings.role == UserRole.restricted:
        await update.message.reply_html(
            "<b>Yoink Bot</b>\n\n"
            "Your account is pending approval. "
            "An admin will grant you access shortly."
        )
        return

    if user_settings.blocked:
        await update.message.reply_html("You are banned from using this bot.")
        return

    text = (
        "<b>Yoink Bot</b>\n\n"
        "Send me a link and I'll download it for you.\n\n"
        "Supported: YouTube, Instagram, TikTok, Twitter/X, Reddit, and "
        "<a href='https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md'>1000+ more</a>."
    )
    await update.message.reply_html(text, link_preview_options=LinkPreviewOptions(is_disabled=True))


async def _help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    user_repo = get_user_repo(context)
    user = await user_repo.get_or_create(update.effective_user.id)
    role = user.role

    # Build help text from the same role-based command lists as bot_commands.py.
    # Each section matches exactly what the user sees in their command menu.
    sections = _help_sections(role)
    text = "\n\n".join(sections)
    await update.message.reply_html(text)


def _help_sections(role: UserRole) -> list[str]:
    if role == UserRole.banned:
        return ["You are banned from using this bot."]
    if role == UserRole.restricted:
        return ["Your account is pending approval. An admin will grant you access shortly."]

    sections: list[str] = []

    # Core download commands  - always visible
    sections.append(
        "<b>Download</b>\n"
        "/video &lt;url&gt;  - download video\n"
        "/audio &lt;url&gt;  - download audio\n"
        "/image &lt;url&gt;  - download images via gallery-dl\n"
        "/cut &lt;url&gt; &lt;start&gt; &lt;end&gt;  - cut a clip\n"
        "/playlist &lt;url&gt;  - playlist download\n"
        "/link &lt;url&gt;  - get direct download link\n"
        "/search &lt;query&gt;  - search YouTube\n\n"
        "You can also send any URL directly in private chat."
    )

    # Settings  - collapsed, everyone has these
    sections.append(
        "<blockquote expandable><b>Settings</b>\n"
        "/settings  - overview\n"
        "/format  - video quality\n"
        "/lang  - language\n"
        "/proxy  - proxy toggle\n"
        "/split  - split size\n"
        "/subs  - subtitles\n"
        "/nsfw  - NSFW blur\n"
        "/mediainfo  - mediainfo report toggle\n"
        "/cookie  - manage cookies\n"
        "/clean  - reset settings to defaults</blockquote>"
    )

    if role in (UserRole.moderator, UserRole.admin, UserRole.owner):
        sections.append(
            "<blockquote expandable><b>Moderator</b>\n"
            "/get_log &lt;user_id&gt;  - user download log\n"
            "/usage &lt;user_id&gt;  - usage statistics</blockquote>"
        )

    if role in (UserRole.admin, UserRole.owner):
        sections.append(
            "<blockquote expandable><b>Admin</b>\n"
            "/block &lt;user_id&gt;  - block user\n"
            "/unblock &lt;user_id&gt;  - unblock user\n"
            "/ban_time &lt;user_id&gt; &lt;hours&gt;  - temporary ban\n"
            "/broadcast &lt;text&gt;  - message all users\n"
            "/uncache &lt;url&gt;  - remove URL from cache\n"
            "/reload_cache  - reload file cache\n"
            "/group enable|disable  - activate/silence bot in a group\n"
            "/group info|allow_pm|nsfw|role  - group settings\n"
            "/thread allow|deny|list|reset  - thread access</blockquote>"
        )

    if role == UserRole.owner:
        sections.append(
            "<blockquote expandable><b>Owner</b>\n"
            "/runtime  - bot runtime info</blockquote>"
        )

    return sections


def register(app: Application) -> None:
    # /start and /help only in private chats  - groups don't need onboarding
    app.add_handler(CommandHandler("start", _start, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("help", _help, filters=filters.ChatType.PRIVATE))
