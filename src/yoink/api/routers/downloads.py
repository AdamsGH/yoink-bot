"""Download history endpoints."""
from __future__ import annotations

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.api.deps import get_current_user, get_db, require_role
from yoink.api.schemas import DownloadListResponse, DownloadLogResponse, RetryResponse
from yoink.storage.models import DownloadLog, Group, User, UserRole

router = APIRouter(prefix="/downloads", tags=["downloads"])

_MOD_ROLES = (UserRole.owner, UserRole.admin, UserRole.moderator)


def _log_to_response(dl: DownloadLog, group_title: str | None = None) -> DownloadLogResponse:
    return DownloadLogResponse(
        id=dl.id,
        user_id=dl.user_id,
        url=dl.url,
        domain=dl.domain,
        title=dl.title,
        quality=dl.quality,
        file_size=dl.file_size,
        duration=dl.duration,
        status=dl.status,
        error_msg=dl.error_msg,
        group_id=dl.group_id,
        group_title=group_title,
        thread_id=dl.thread_id,
        message_id=dl.message_id,
        clip_start=dl.clip_start,
        clip_end=dl.clip_end,
        created_at=dl.created_at,
    )


@router.get("", response_model=DownloadListResponse)
async def get_my_downloads(
    page: int = 1,
    limit: int = 20,
    status: str | None = None,
    domain: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DownloadListResponse:
    """Return the authenticated user's download history (paginated)."""
    from datetime import datetime as dt
    offset = (page - 1) * limit

    where = [DownloadLog.user_id == current_user.id]
    if status:
        where.append(DownloadLog.status == status)
    if domain:
        where.append(DownloadLog.domain == domain)
    if search:
        like = f"%{search}%"
        from sqlalchemy import or_
        where.append(or_(DownloadLog.title.ilike(like), DownloadLog.url.ilike(like)))
    if date_from:
        where.append(DownloadLog.created_at >= dt.fromisoformat(date_from))
    if date_to:
        where.append(DownloadLog.created_at <= dt.fromisoformat(date_to))

    total_result = await session.execute(
        select(func.count()).select_from(DownloadLog).where(*where)
    )
    total = total_result.scalar_one()

    result = await session.execute(
        select(DownloadLog, Group.title.label("group_title"))
        .outerjoin(Group, DownloadLog.group_id == Group.id)
        .where(*where)
        .order_by(DownloadLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()

    return DownloadListResponse(
        items=[_log_to_response(dl, group_title) for dl, group_title in rows],
        total=total,
    )


@router.get("/all", response_model=DownloadListResponse)
async def get_all_downloads(
    page: int = 1,
    limit: int = 20,
    user_id: int | None = None,
    domain: str | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_db),
    _mod: User = Depends(require_role(*_MOD_ROLES)),
) -> DownloadListResponse:
    """Return all users' download history (moderator+). Supports filters."""
    offset = (page - 1) * limit

    filters = []
    if user_id is not None:
        filters.append(DownloadLog.user_id == user_id)
    if domain is not None:
        filters.append(DownloadLog.domain == domain)
    if status is not None:
        filters.append(DownloadLog.status == status)

    total_result = await session.execute(
        select(func.count()).select_from(DownloadLog).where(*filters)
    )
    total = total_result.scalar_one()

    result = await session.execute(
        select(DownloadLog, Group.title.label("group_title"))
        .outerjoin(Group, DownloadLog.group_id == Group.id)
        .where(*filters)
        .order_by(DownloadLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()

    return DownloadListResponse(
        items=[_log_to_response(dl, group_title) for dl, group_title in rows],
        total=total,
    )


@router.post("/{log_id}/retry", response_model=RetryResponse)
async def retry_download(
    log_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetryResponse:
    """Re-send the URL from a history entry to the bot as a message.

    The bot receives it as a normal user message and processes it through
    the standard download pipeline. This allows retrying failed downloads
    or re-downloading from history via the Mini App.
    """
    result = await session.execute(
        select(DownloadLog).where(
            DownloadLog.id == log_id,
            DownloadLog.user_id == current_user.id,
        )
    )
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="Download log entry not found")

    settings = request.app.state.settings
    base_url = settings.telegram_base_url.rstrip("/")
    token = settings.bot_token
    api_url = f"{base_url}{token}/sendMessage"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(api_url, json={
            "chat_id": current_user.id,
            "text": log.url,
        })

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to send message to Telegram")

    return RetryResponse(url=log.url, queued=True)
