"""
Admin commands: /block, /unblock, /ban_time, /broadcast,
                /uncache, /reload_cache, /get_log, /usage, /runtime

All commands require owner or admin role (guard_role check).
Usage patterns:
  /block <user_id> [reason]
  /unblock <user_id>
  /ban_time <user_id> <duration>  e.g. 1h 30m 7d
  /broadcast <text>
  /uncache <url>
  /reload_cache
  /get_log <user_id> [limit]
  /usage [user_id]
  /runtime
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from yoink.bot.middleware import get_session_factory, get_settings, get_user_repo
from yoink.i18n.loader import t
from yoink.storage.models import DownloadLog, User, UserRole
from yoink.utils.formatting import format_size, humantime

logger = logging.getLogger(__name__)

_start_time = time.monotonic()


async def _guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Allow owner and admin roles only."""
    if not update.message or not update.effective_user:
        return False
    repo = get_user_repo(context)
    user = await repo.get_or_create(update.effective_user.id)
    if user.role not in (UserRole.owner, UserRole.admin):
        await update.message.reply_text(t("admin.access_denied", "en"))
        return False
    return True


def _parse_duration(s: str) -> timedelta | None:
    """Parse duration string like '1h', '30m', '7d', '2h30m' into timedelta."""
    import re
    total = timedelta()
    pattern = re.compile(r"(\d+)\s*([smhd])")
    matches = pattern.findall(s.lower())
    if not matches:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    for val, unit in matches:
        total += timedelta(seconds=int(val) * units[unit])
    return total if total.total_seconds() > 0 else None


async def _cmd_block(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await _guard(update, context):
        return
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_html(
            "Usage: <code>/block &lt;user_id&gt; [reason]</code>"
        )
        return
    target_id = int(args[0])
    reason = " ".join(args[1:]) if len(args) > 1 else None

    repo = get_user_repo(context)
    await repo.update(target_id, role=UserRole.banned)

    lang = (await repo.get_or_create(update.effective_user.id)).language  # type: ignore[union-attr]
    msg = t("admin.user_blocked", lang, user_id=target_id)
    if reason:
        msg += f"\nReason: {reason}"
    await update.message.reply_html(msg)
    logger.info("User %d blocked by admin %d (reason=%s)", target_id, update.effective_user.id, reason)  # type: ignore[union-attr]


async def _cmd_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await _guard(update, context):
        return
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_html(
            "Usage: <code>/unblock &lt;user_id&gt;</code>"
        )
        return
    target_id = int(args[0])

    repo = get_user_repo(context)
    await repo.update(target_id, role=UserRole.user, ban_until=None)

    lang = (await repo.get_or_create(update.effective_user.id)).language  # type: ignore[union-attr]
    await update.message.reply_html(t("admin.user_unblocked", lang, user_id=target_id))


async def _cmd_ban_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await _guard(update, context):
        return
    args = context.args or []
    if len(args) < 2 or not args[0].isdigit():
        await update.message.reply_html(
            "Usage: <code>/ban_time &lt;user_id&gt; &lt;duration&gt;</code>\n"
            "Duration: <code>30m</code>, <code>1h</code>, <code>7d</code>, <code>2h30m</code>"
        )
        return

    target_id = int(args[0])
    duration_str = " ".join(args[1:])
    delta = _parse_duration(duration_str)
    if not delta:
        await update.message.reply_html("❌ Invalid duration format.")
        return

    ban_until = datetime.now(timezone.utc) + delta
    repo = get_user_repo(context)
    await repo.update(target_id, ban_until=ban_until)

    lang = (await repo.get_or_create(update.effective_user.id)).language  # type: ignore[union-attr]
    await update.message.reply_html(
        t("admin.ban_set", lang, user_id=target_id, duration=duration_str)
    )


async def _cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await _guard(update, context):
        return
    args = context.args or []
    text = " ".join(args).strip()
    if not text:
        await update.message.reply_html(
            "Usage: <code>/broadcast &lt;message text&gt;</code>"
        )
        return

    session_factory = get_session_factory(context)
    async with session_factory() as session:
        result = await session.execute(
            select(User.id).where(User.role != UserRole.banned)
        )
        user_ids = [row[0] for row in result.fetchall()]

    status = await update.message.reply_html(
        t("admin.broadcast_started", "en", count=len(user_ids))
    )

    sent = failed = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        # Telegram allows ~30 msg/s to different users; stay well under
        await asyncio.sleep(0.05)

    await status.edit_text(
        t("admin.broadcast_done", "en", sent=sent, failed=failed),
        parse_mode="HTML",
    )


async def _cmd_uncache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await _guard(update, context):
        return
    args = context.args or []
    if not args:
        await update.message.reply_html(
            "Usage: <code>/uncache &lt;url&gt;</code>"
        )
        return
    url = args[0]
    file_cache = context.bot_data.get("file_cache")
    if not file_cache:
        await update.message.reply_text("Cache not available.")
        return

    from yoink.storage.file_cache import make_cache_key
    from yoink.url.normalizer import normalize
    from yoink.url.domains import DomainConfig

    settings = get_settings(context)
    domain_cfg = DomainConfig.from_settings(settings)
    normalized = normalize(url, domain_cfg)
    key = make_cache_key(normalized)
    removed = await file_cache.delete(key)

    if removed:
        await update.message.reply_html(f"✅ Cache cleared for:\n<code>{url}</code>")
    else:
        await update.message.reply_html(f"⚠️ No cache entry found for:\n<code>{url}</code>")


async def _cmd_reload_cache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await _guard(update, context):
        return
    # File cache is DB-backed  - just confirm it's alive
    file_cache = context.bot_data.get("file_cache")
    if not file_cache:
        await update.message.reply_text("Cache not available.")
        return
    await update.message.reply_html(t("admin.cache_reloaded", "en"))


async def _cmd_get_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await _guard(update, context):
        return
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_html(
            "Usage: <code>/get_log &lt;user_id&gt; [limit]</code>"
        )
        return

    target_id = int(args[0])
    limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
    limit = min(limit, 50)

    session_factory = get_session_factory(context)
    async with session_factory() as session:
        result = await session.execute(
            select(DownloadLog)
            .where(DownloadLog.user_id == target_id)
            .order_by(DownloadLog.created_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()

    if not logs:
        await update.message.reply_html(
            t("admin.no_logs", "en", user_id=target_id)
        )
        return

    lines = [t("admin.logs_title", "en", user_id=target_id)]
    for log in logs:
        ts = log.created_at.strftime("%Y-%m-%d %H:%M")
        size = format_size(log.file_size) if log.file_size else "?"
        title = (log.title or log.url or "")[:60]
        status_icon = "✅" if log.status == "ok" else "❌"
        lines.append(f"{status_icon} <code>{ts}</code> {size}\n   {title}")

    text = "\n\n".join(lines)
    for chunk in [text[i:i + 4000] for i in range(0, len(text), 4000)]:
        await update.message.reply_html(chunk)


async def _cmd_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await _guard(update, context):
        return
    args = context.args or []
    target_id = int(args[0]) if args and args[0].isdigit() else (update.effective_user.id if update.effective_user else 0)  # type: ignore[union-attr]

    session_factory = get_session_factory(context)
    async with session_factory() as session:
        total_result = await session.execute(
            select(func.count(), func.coalesce(func.sum(DownloadLog.file_size), 0))
            .where(DownloadLog.user_id == target_id)
            .where(DownloadLog.status == "ok")
        )
        total_count, total_size = total_result.one()

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await session.execute(
            select(func.count())
            .where(DownloadLog.user_id == target_id)
            .where(DownloadLog.created_at >= today_start)
            .where(DownloadLog.status == "ok")
        )
        today_count = today_result.scalar() or 0

    lang = (await get_user_repo(context).get_or_create(update.effective_user.id)).language  # type: ignore[union-attr]
    lines = [
        t("usage.title", lang),
        t("usage.downloads", lang, count=total_count),
        t("usage.total_size", lang, size=format_size(total_size or 0)),
        t("usage.today", lang, count=today_count),
    ]
    if target_id != update.effective_user.id:  # type: ignore[union-attr]
        lines.insert(1, f"User: <code>{target_id}</code>")

    await update.message.reply_html("\n".join(lines))


async def _cmd_runtime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await _guard(update, context):
        return
    elapsed_ms = (time.monotonic() - _start_time) * 1000
    lang = (await get_user_repo(context).get_or_create(update.effective_user.id)).language  # type: ignore[union-attr]
    await update.message.reply_html(
        t("admin.runtime", lang, uptime=humantime(elapsed_ms))
    )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("block", _cmd_block))
    app.add_handler(CommandHandler("unblock", _cmd_unblock))
    app.add_handler(CommandHandler("ban_time", _cmd_ban_time))
    app.add_handler(CommandHandler("broadcast", _cmd_broadcast))
    app.add_handler(CommandHandler("uncache", _cmd_uncache))
    app.add_handler(CommandHandler("reload_cache", _cmd_reload_cache))
    app.add_handler(CommandHandler("get_log", _cmd_get_log))
    app.add_handler(CommandHandler("usage", _cmd_usage))
    app.add_handler(CommandHandler("runtime", _cmd_runtime))
