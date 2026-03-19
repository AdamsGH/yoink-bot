"""
/settings  - overview of all user preferences with quick-access buttons.
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from yoink.bot.middleware import get_user_repo
from yoink.i18n.loader import t
from yoink.storage.user_settings import UserSettings
from yoink.utils.formatting import format_size


def _yn(value: bool, lang: str) -> str:
    return t("common.on", lang) if value else t("common.off", lang)


def _status_text(user: UserSettings) -> str:
    lang = user.language
    return t(
        "settings.title",
        lang,
        language=user.language.upper(),
        quality=user.quality,
        codec=user.codec,
        container=user.container,
        proxy=_yn(user.proxy_enabled, lang),
        keyboard=user.keyboard,
        subs=_yn(user.subs_enabled, lang),
        split_size=format_size(user.split_size),
        nsfw_blur=_yn(user.nsfw_blur, lang),
        mediainfo=_yn(user.mediainfo, lang),
    )


def _keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Format", callback_data="settings:goto:format"),
            InlineKeyboardButton("🌐 Language", callback_data="settings:goto:lang"),
        ],
        [
            InlineKeyboardButton("🔀 Proxy", callback_data="settings:goto:proxy"),
            InlineKeyboardButton("✂️ Split", callback_data="settings:goto:split"),
        ],
        [
            InlineKeyboardButton("📝 Subs", callback_data="settings:goto:subs"),
            InlineKeyboardButton("🔞 NSFW", callback_data="settings:goto:nsfw"),
        ],
        [
            InlineKeyboardButton("ℹ️ Mediainfo", callback_data="settings:goto:mediainfo"),
            InlineKeyboardButton("⌨️ Keyboard", callback_data="settings:goto:keyboard"),
        ],
        [
            InlineKeyboardButton("🔧 Args", callback_data="settings:goto:args"),
            InlineKeyboardButton("🍪 Cookies", callback_data="settings:goto:cookie"),
        ],
    ])


async def _cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    repo = get_user_repo(context)
    user = await repo.get_or_create(update.effective_user.id)
    await update.message.reply_html(_status_text(user), reply_markup=_keyboard(user.language))


def register(app: Application) -> None:
    app.add_handler(CommandHandler("settings", _cmd_settings))
