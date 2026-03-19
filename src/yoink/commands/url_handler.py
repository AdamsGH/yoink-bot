"""
Main URL message handler - wires the full download pipeline.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from telegram import Bot, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from yoink.bot.middleware import get_session_factory, get_settings, get_user_repo, is_blocked
from yoink.bot.progress import ProgressTracker, register as reg_tracker, unregister as unreg_tracker
from yoink.download.manager import DownloadJob, DownloadManager
from yoink.download.postprocess import postprocess_all
from yoink.services.cookies import CookieManager
from yoink.services.nsfw import NsfwChecker
from yoink.storage.download_log import DownloadLogRepo
from yoink.storage.file_cache import CachedFile, FileCacheRepo, make_cache_key
from yoink.storage.group_repo import GroupRepo
from yoink.storage.rate_limit import RateLimitRepo
from yoink.upload.caption import build_caption, build_group_caption
from yoink.upload.sender import MediaMeta, SendResult, send_files
from yoink.utils.errors import BotError
from yoink.utils.formatting import humanbytes
from yoink.utils.mediainfo import get_report as mediainfo_report
from yoink.utils.safe_telegram import delete_many
from yoink.url.clip import ClipSpec, extract_t_param, parse_clip_spec
from yoink.url.domains import DomainConfig
from yoink.url.extractor import extract_url
from yoink.url.normalizer import normalize
from yoink.url.resolver import resolve

logger = logging.getLogger(__name__)

_AWAITING_CLIP_END = "awaiting_clip_end"


async def _chat_action_loop(
    bot: Bot,
    chat_id: int,
    action: str,
    thread_id: int | None,
    stop: asyncio.Event,
) -> None:
    """Send chat action every 4s until stop is set (Telegram clears it after 5s)."""
    kw: dict[str, Any] = {"chat_id": chat_id, "action": action}
    if thread_id:
        kw["message_thread_id"] = thread_id
    try:
        while not stop.is_set():
            try:
                await bot.send_chat_action(**kw)
            except Exception:
                pass
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass


def _get_file_cache(context: ContextTypes.DEFAULT_TYPE) -> FileCacheRepo | None:
    return context.bot_data.get("file_cache")


def _get_group_repo(context: ContextTypes.DEFAULT_TYPE) -> GroupRepo | None:
    return context.bot_data.get("group_repo")


def _get_nsfw_checker(context: ContextTypes.DEFAULT_TYPE) -> NsfwChecker | None:
    return context.bot_data.get("nsfw_checker")


def _get_bot_settings_repo(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data.get("bot_settings_repo")


_ROLE_ORDER = ["owner", "admin", "moderator", "user", "restricted", "banned"]


async def _can_use_browser_cookies(
    user_id: int,
    user_role: str,
    settings: "Settings",
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    if not settings.browser_cookies_available():
        return False
    repo = _get_bot_settings_repo(context)
    if repo is None:
        return user_id == settings.owner_id
    min_role = await repo.get_browser_cookies_min_role()
    min_idx = _ROLE_ORDER.index(min_role.value) if min_role.value in _ROLE_ORDER else 0
    user_idx = _ROLE_ORDER.index(user_role) if user_role in _ROLE_ORDER else len(_ROLE_ORDER)
    return user_idx <= min_idx


def _extract_file_id(result: SendResult) -> tuple[str, str] | None:
    """Return (file_id, file_type) from a SendResult, or None."""
    msg = result.message
    if msg.video:
        return msg.video.file_id, "video"
    if msg.document:
        return msg.document.file_id, "document"
    if msg.audio:
        return msg.audio.file_id, "audio"
    return None


def _get_thread_id(update: Update) -> int | None:
    """Extract message_thread_id for supergroup forum topics; None otherwise."""
    msg = update.message
    if msg and msg.is_topic_message:
        return msg.message_thread_id
    return None


async def _check_group_access(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """
    For group/supergroup messages: ensure the group is registered and the
    thread (if any) is allowed. Returns True if processing should continue.

    DM messages always pass.
    """
    chat = update.effective_chat
    if chat is None or chat.type not in ("group", "supergroup"):
        return True

    group_repo = _get_group_repo(context)
    if group_repo is None:
        # No group repo - allow everything (bot running without group support)
        return True

    group_id = chat.id
    thread_id = _get_thread_id(update)

    # Auto-register the group on first contact (enabled=False by default)
    title = chat.title or str(group_id)
    await group_repo.upsert(group_id=group_id, title=title)

    if not await group_repo.is_enabled(group_id):
        logger.debug("Message blocked: group=%d not enabled", group_id)
        return False

    allowed = await group_repo.is_thread_allowed(group_id, thread_id)
    if not allowed:
        logger.debug(
            "Message blocked: group=%d thread=%s not allowed",
            group_id, thread_id,
        )
    return allowed


async def _run_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    url: str,
    clip: ClipSpec | None,
    playlist_start: int | None = None,
    playlist_end: int | None = None,
    target_chat_id: int | None = None,
) -> None:
    # target_chat_id is set when called from a callback (ask_menu, cut)
    # so we send to the right chat without trying to reply to a deleted message
    assert update.effective_user
    use_message = update.message  # may be None when called from callback
    chat_id = target_chat_id or (use_message.chat_id if use_message else None)
    assert chat_id

    user_id = update.effective_user.id

    if await is_blocked(user_id, context):
        return

    thread_id = _get_thread_id(update)
    settings = get_settings(context)
    user_repo = get_user_repo(context)
    user_settings = await user_repo.get_or_create(user_id)

    # Rate-limit (skip for owner); applies in both private and group contexts
    if user_id != settings.owner_id:
        session_factory = get_session_factory(context)
        async with session_factory() as session:
            rl = RateLimitRepo(session)
            allowed, reason = await rl.check_and_increment(
                user_id=user_id,
                limit_minute=settings.rate_limit_per_minute,
                limit_hour=settings.rate_limit_per_hour,
                limit_day=settings.rate_limit_per_day,
            )
            await session.commit()
        if not allowed:
            from yoink.i18n import t
            msg = t("errors.rate_limited", user_settings.language) + f"\n<i>({reason})</i>"
            if use_message:
                await use_message.reply_html(msg)
            return

    # Apply one-shot quality override from "always ask" menu
    quality_override = context.user_data.pop("_ask_quality_override", None)
    if quality_override:
        import dataclasses
        user_settings = dataclasses.replace(user_settings, quality=quality_override)

    file_cache: FileCacheRepo | None = _get_file_cache(context)
    dl_log: DownloadLogRepo | None = context.bot_data.get("download_log")
    cookie_mgr: CookieManager | None = context.bot_data.get("cookie_manager")

    domain_cfg = DomainConfig.from_settings(settings)
    url = normalize(url, domain_cfg)

    chat = update.effective_chat
    is_private = (chat.type == "private") if chat else True
    group_id: int | None = None
    if chat and chat.type in ("group", "supergroup"):
        group_id = chat.id

    # Cache lookup
    cache_key = make_cache_key(
        url,
        start_sec=clip.start_sec if clip else None,
        end_sec=clip.end_sec if clip else None,
    )
    if cache_key and file_cache:
        cached = await file_cache.get(cache_key)
        if cached:
            logger.info("Cache hit for %s (file_id=%s…)", url, cached.file_id[:12])
            nsfw_checker = _get_nsfw_checker(context)
            cached_nsfw, _ = nsfw_checker.check(url) if nsfw_checker else (False, "")
            if is_private:
                cached_caption = build_caption(title=cached.title or "", url=url, settings=settings)
                cached_has_spoiler = NsfwChecker.should_apply_spoiler(
                    is_nsfw_content=cached_nsfw,
                    user_nsfw_blur=user_settings.nsfw_blur,
                    is_private_chat=True,
                )
            else:
                tg_user = update.effective_user
                requester = tg_user.first_name or tg_user.username or str(user_id)
                cached_caption = build_group_caption(url=url, requester_name=requester, requester_id=user_id)
                cached_has_spoiler = cached_nsfw
            cached_reply_to = (use_message.message_id if use_message else None) if is_private else None
            try:
                sent = await _send_cached(
                    bot=context.bot,
                    chat_id=chat_id,
                    cached=cached,
                    caption=cached_caption,
                    reply_to=cached_reply_to,
                    thread_id=thread_id,
                    send_as_file=user_settings.send_as_file,
                    has_spoiler=cached_has_spoiler,
                )
                if use_message:
                    await delete_many(context.bot, chat_id, [use_message.message_id])
                if dl_log:
                    await dl_log.write(
                        user_id=user_id,
                        url=url,
                        title=cached.title,
                        file_size=cached.file_size,
                        duration=cached.duration,
                        status="cached",
                        group_id=group_id,
                        thread_id=thread_id,
                        message_id=sent.message_id,
                    )
                return
            except Exception:
                logger.warning("Cache send failed for %s, falling through to download", url)

    status_kw: dict[str, Any] = {"chat_id": chat_id, "text": "Fetching…"}
    if thread_id:
        status_kw["message_thread_id"] = thread_id
    status = await context.bot.send_message(**status_kw)
    tracker = ProgressTracker(status)
    reg_tracker(tracker)

    try:
        resolved = resolve(
            url,
            domain_cfg,
            proxy_enabled=user_settings.proxy_enabled,
            custom_proxy_url=user_settings.proxy_url if user_settings.proxy_enabled else None,
            playlist_start=playlist_start,
            playlist_end=playlist_end,
        )

        cookie_path: Path | None = None
        if cookie_mgr:
            cookie_path = await cookie_mgr.get_path_for_url(
                user_id=user_id,
                url=url,
                global_user_id=settings.owner_id,
                no_cookie_domains=domain_cfg.no_cookie,
            )

        force_mode = context.user_data.pop("force_mode", None)
        audio_only = force_mode == "audio"
        multi_clips: list = context.user_data.pop("_clips", [])

        from yoink.url.resolver import Engine
        engine_override = Engine.GALLERY_DL if force_mode == "gallery" else None

        # NSFW Layer 1+2: domain / URL keyword check before downloading
        nsfw_checker: NsfwChecker | None = _get_nsfw_checker(context)
        user_forced_nsfw: bool = bool(context.user_data.pop("force_nsfw", False))
        content_is_nsfw = user_forced_nsfw

        if nsfw_checker and not content_is_nsfw:
            nsfw_hit, nsfw_reason = nsfw_checker.check(url)
            if nsfw_hit:
                content_is_nsfw = True
                logger.info("nsfw pre-check: user=%d url=%s reason=%s", user_id, url, nsfw_reason)

        # NSFW Layer 3 (group policy): block NSFW content in groups that don't allow it
        if content_is_nsfw and group_id and not is_private:
            group_repo: GroupRepo | None = _get_group_repo(context)
            if group_repo:
                group = await group_repo.get(group_id)
                if group and not group.nsfw_allowed:
                    await status.edit_text("🔞 NSFW content is not allowed in this group.")
                    return

        download_dir = Path(tempfile.mkdtemp(prefix="yoink_"))
        job = DownloadJob(
            user_id=user_id,
            resolved=resolved,
            settings=user_settings,
            download_dir=download_dir,
            clip=clip,
            clips=multi_clips,
            cookie_path=cookie_path,
            audio_only=audio_only,
            engine_override=engine_override,
            use_browser_cookies=await _can_use_browser_cookies(user_id, user_settings.role, settings, context),
        )

        manager = DownloadManager(settings=settings)
        _action_stop = asyncio.Event()
        if audio_only:
            _upload_action = ChatAction.UPLOAD_VOICE
        elif user_settings.send_as_file:
            _upload_action = ChatAction.UPLOAD_DOCUMENT
        else:
            _upload_action = ChatAction.UPLOAD_VIDEO
        _action_task = asyncio.create_task(
            _chat_action_loop(context.bot, chat_id, _upload_action, thread_id, _action_stop)
        )
        try:
            job = await manager.run(job, progress_cb=tracker.ytdlp_hook)
        finally:
            _action_stop.set()
            _action_task.cancel()

        # NSFW Layer 3: metadata check (title/tags/description from yt-dlp)
        if nsfw_checker and not content_is_nsfw and job.info:
            nsfw_hit, nsfw_reason = nsfw_checker.check(url, info=job.info)
            if nsfw_hit:
                content_is_nsfw = True
                logger.info("nsfw meta-check: user=%d url=%s reason=%s", user_id, url, nsfw_reason)
                # Re-check group policy now that we have metadata
                if group_id and not is_private:
                    group_repo = _get_group_repo(context)
                    if group_repo:
                        group = await group_repo.get(group_id)
                        if group and not group.nsfw_allowed:
                            await status.edit_text("🔞 NSFW content is not allowed in this group.")
                            return

        # In groups: NSFW content always gets spoiler if group allows it through
        if is_private:
            has_spoiler = NsfwChecker.should_apply_spoiler(
                is_nsfw_content=content_is_nsfw,
                user_nsfw_blur=user_settings.nsfw_blur,
                is_private_chat=True,
            )
        else:
            has_spoiler = content_is_nsfw

        files = await postprocess_all(job.files)
        files = [f for f in files if f.exists()]
        file_size = sum(f.stat().st_size for f in files)

        tracker.set_phase("upload")
        await status.edit_text(f"Uploading {humanbytes(file_size)}…")

        meta = MediaMeta(
            duration=int(job.duration),
            width=job.width,
            height=job.height,
            thumb=job.thumb,
        )

        if is_private:
            clip_extra = ""
            if clip:
                def _fmt_s(s: int) -> str:
                    h, r = divmod(s, 3600); m, sec = divmod(r, 60)
                    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
                clip_extra = f"✂️ {_fmt_s(clip.start_sec)} → {_fmt_s(clip.end_sec)}"
            caption = build_caption(
                title=job.title,
                url=resolved.url,
                settings=settings,
                extra=clip_extra,
            )
            reply_to = use_message.message_id if use_message else None
        else:
            tg_user = update.effective_user
            requester = tg_user.first_name or tg_user.username or str(user_id)
            caption = build_group_caption(url=resolved.url, requester_name=requester, requester_id=user_id)
            reply_to = None

        results = await send_files(
            bot=context.bot,
            chat_id=chat_id,
            files=files,
            caption=caption,
            reply_to=reply_to,
            thread_id=thread_id,
            meta=meta,
            send_as_file=user_settings.send_as_file,
            has_spoiler=has_spoiler,
            show_caption_above_media=is_private,
        )

        # Delete status message always; delete user's command in both private and group.
        # reply_parameters uses allow_sending_without_reply=True so deleting the
        # command before the bot replies does not cause an error.
        to_delete = [status.message_id]
        if use_message:
            to_delete.append(use_message.message_id)
        await delete_many(context.bot, chat_id, to_delete)

        # Mediainfo report  - sent after media, only if user opted in and single file
        if user_settings.mediainfo and len(files) == 1 and is_private:
            report = await mediainfo_report(files[0])
            if report:
                sent_id = results[0].message.message_id if results else None
                from telegram import ReplyParameters
                kw: dict = {"chat_id": chat_id, "text": report, "parse_mode": ParseMode.HTML}
                if sent_id:
                    kw["reply_parameters"] = ReplyParameters(
                        message_id=sent_id, allow_sending_without_reply=True
                    )
                if thread_id:
                    kw["message_thread_id"] = thread_id
                try:
                    await context.bot.send_message(**kw)
                except Exception as e:
                    logger.warning("Failed to send mediainfo report: %s", e)

        sent_message_id: int | None = results[0].message.message_id if results else None
        if dl_log:
            await dl_log.write(
                user_id=user_id,
                url=url,
                title=job.title,
                quality=user_settings.quality,
                file_size=file_size,
                duration=job.duration,
                group_id=group_id,
                thread_id=thread_id,
                message_id=sent_message_id,
                clip_start=clip.start_sec if clip else None,
                clip_end=clip.end_sec if clip else None,
            )

        # Cache first file for single-file downloads
        if cache_key and file_cache and results and len(files) == 1:
            id_pair = _extract_file_id(results[0])
            if id_pair:
                file_id, file_type = id_pair
                await file_cache.store(CachedFile(
                    cache_key=cache_key,
                    file_id=file_id,
                    file_type=file_type,
                    title=job.title,
                    duration=job.duration,
                    width=job.width,
                    height=job.height,
                    file_size=file_size,
                ))

    except BotError as e:
        from yoink.i18n import t
        lang = user_settings.language if user_settings else "en"
        await status.edit_text(t(e.message_key, lang, **e.kwargs), parse_mode=ParseMode.HTML)
        if dl_log:
            await dl_log.write(
                user_id=user_id, url=url, status="error", error_msg=e.message_key,
                group_id=group_id, thread_id=thread_id,
            )
    except Exception as e:
        logger.exception("Unhandled error for url %s user %d", url, user_id)
        await status.edit_text("Something went wrong. Please try again.")
        if dl_log:
            await dl_log.write(
                user_id=user_id, url=url, status="error", error_msg=str(e)[:200],
                group_id=group_id, thread_id=thread_id,
            )
    finally:
        unreg_tracker(tracker)


async def _send_cached(
    bot: Bot,
    chat_id: int,
    cached: CachedFile,
    caption: str,
    reply_to: int | None,
    thread_id: int | None,
    send_as_file: bool,
    has_spoiler: bool = False,
) -> Message:
    from telegram import ReplyParameters
    common: dict[str, Any] = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": ParseMode.HTML,
    }
    if reply_to:
        common["reply_parameters"] = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True)
    if thread_id:
        common["message_thread_id"] = thread_id

    file_type = "document" if send_as_file else cached.file_type

    if file_type == "video":
        return await bot.send_video(video=cached.file_id, has_spoiler=has_spoiler, **common)
    elif file_type == "audio":
        return await bot.send_audio(audio=cached.file_id, **common)
    else:
        return await bot.send_document(document=cached.file_id, **common)


async def _handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id

    # Drop stale messages accumulated while bot was offline
    msg_age = time.time() - update.message.date.timestamp()
    if msg_age > 30:
        logger.debug("Dropping stale message (age=%.0fs) from user %d", msg_age, user_id)
        return

    # Check if we're waiting for clip end time from this user
    if context.user_data.get(_AWAITING_CLIP_END):
        await _handle_clip_end_time(update, context)
        return

    # Check if a /cut interactive session is active
    from yoink.commands.cut import handle_cut_input as _cut_input
    if await _cut_input(update, context):
        return

    # Check if ask_menu is awaiting a time input for a segment
    from yoink.commands.ask_menu import handle_time_input as _am_input
    if await _am_input(update, context):
        return

    url = extract_url(update.message)
    if not url:
        return

    text = update.message.text or ""

    try:
        clip = parse_clip_spec(url, text)
    except ValueError as e:
        await update.message.reply_text(
            f"Invalid time format: {e}\nUse HH:MM:SS, MM:SS, or plain seconds."
        )
        return

    if clip is None:
        t_sec = extract_t_param(url)
        if t_sec is not None:
            context.user_data[_AWAITING_CLIP_END] = {"url": url, "start_sec": t_sec}
            await update.message.reply_text(
                f"Start time: <b>{_fmt_sec(t_sec)}</b>\n"
                "Send end time or duration (e.g. <code>00:26:10</code> or <code>60</code>):",
                parse_mode=ParseMode.HTML,
            )
            return

    # "Always ask" mode  - show quality picker instead of downloading immediately
    user_repo = get_user_repo(context)
    user_settings_pre = await user_repo.get_or_create(user_id)
    if user_settings_pre.quality == "ask" and not context.user_data.get("force_mode"):
        from yoink.commands.ask_menu import show_menu as _show_menu
        await _show_menu(update, context, url)
        return

    await _run_download(update, context, url, clip)


async def _handle_clip_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user's response when we asked for clip end time."""
    data = context.user_data.pop(_AWAITING_CLIP_END)
    url: str = data["url"]
    start_sec: int = data["start_sec"]
    text = (update.message.text or "").strip()  # type: ignore[union-attr]

    try:
        from yoink.url.clip import parse_time
        end_sec = parse_time(text) if ":" in text else start_sec + int(text)
    except (ValueError, TypeError):
        await update.message.reply_text(  # type: ignore[union-attr]
            "Invalid format. Use HH:MM:SS, MM:SS, or plain seconds."
        )
        return

    if end_sec <= start_sec:
        await update.message.reply_text("End time must be after start time.")  # type: ignore[union-attr]
        return

    await _run_download(update, context, url, ClipSpec(start_sec=start_sec, end_sec=end_sec))


def _fmt_sec(secs: int) -> str:
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def register(app: Application) -> None:
    # Private chats: respond to any plain-text URL.
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, _handle_url)
    )
    # Groups: respond only when user replies to the bot's ForceReply prompt.
    # This is safe even in privacy mode  - the bot always receives replies to its own messages.
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.REPLY
            & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
            _handle_group_reply,
        )
    )


async def _handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle URL replies to bot ForceReply prompts in group chats.

    Cleans up the full ForceReply chain (command + bot prompt + user reply)
    after a successful URL is received, keeping the group feed tidy.
    """
    if not update.message or not update.effective_user:
        return
    # Only process if user is replying to a message from this bot
    reply = update.message.reply_to_message
    if not reply or not reply.from_user or not reply.from_user.is_bot:
        return
    me = await context.bot.get_me()
    if reply.from_user.id != me.id:
        return

    url = extract_url(update.message)
    if not url:
        return

    # Collect the full chain to delete: original command + bot prompt + user's reply
    chat_id = update.message.chat_id
    ids_to_delete: list[int] = [update.message.message_id]
    prompt_info: dict | None = context.user_data.pop("_group_prompt", None)
    if prompt_info and prompt_info.get("chat_id") == chat_id:
        if prompt_info.get("prompt_id"):
            ids_to_delete.append(prompt_info["prompt_id"])
        if prompt_info.get("command_id"):
            ids_to_delete.append(prompt_info["command_id"])

    # Delete the chain before starting download so the group looks clean
    await delete_many(context.bot, chat_id, ids_to_delete)

    # Inherit force_mode from the command that triggered ForceReply
    # (stored via context.user_data by /video /audio /image handlers)
    await _run_download(update, context, url, clip=None)
