"""Analytics / stats endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.api.deps import get_db, require_role
from yoink.api.schemas import EventResponse, StatsOverview
from yoink.storage.models import DownloadLog, Event, User, UserRole

router = APIRouter(prefix="/stats", tags=["stats"])

_ADMIN_ROLES = (UserRole.owner, UserRole.admin)


@router.get("/overview", response_model=StatsOverview)
async def stats_overview(
    days: int = 30,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> StatsOverview:
    """Return aggregated statistics (admin+). `days` controls the chart window (7/30/90)."""
    days = max(1, min(days, 365))
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Total downloads ever
    total_result = await session.execute(select(func.count()).select_from(DownloadLog))
    total_downloads = total_result.scalar_one()

    # Downloads today
    today_result = await session.execute(
        select(func.count())
        .select_from(DownloadLog)
        .where(DownloadLog.created_at >= today_start)
    )
    downloads_today = today_result.scalar_one()

    # Cache hits today  - downloads served from file_id cache (status="cached")
    cache_hits_result = await session.execute(
        select(func.count())
        .select_from(DownloadLog)
        .where(DownloadLog.status == "cached", DownloadLog.created_at >= today_start)
    )
    cache_hits_today = cache_hits_result.scalar_one()

    # Errors today
    errors_result = await session.execute(
        select(func.count())
        .select_from(DownloadLog)
        .where(DownloadLog.status == "error", DownloadLog.created_at >= today_start)
    )
    errors_today = errors_result.scalar_one()

    # Top domains (all time, top 10)
    top_domains_result = await session.execute(
        select(DownloadLog.domain, func.count().label("count"))
        .where(DownloadLog.domain.isnot(None))
        .group_by(DownloadLog.domain)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_domains = [{"domain": row.domain, "count": row.count} for row in top_domains_result]

    # Downloads per day for the requested window
    thirty_days_ago = now - timedelta(days=days)
    day_col = func.date_trunc("day", DownloadLog.created_at).label("day")
    by_day_result = await session.execute(
        select(day_col, func.count().label("count"))
        .where(DownloadLog.created_at >= thirty_days_ago)
        .group_by(day_col)
        .order_by(day_col)
    )
    downloads_by_day = [
        {"date": row.day.strftime("%Y-%m-%d"), "count": row.count}
        for row in by_day_result
    ]

    return StatsOverview(
        total_downloads=total_downloads,
        downloads_today=downloads_today,
        cache_hits_today=cache_hits_today,
        errors_today=errors_today,
        top_domains=top_domains,
        downloads_by_day=downloads_by_day,
    )


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    page: int = 1,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> list[EventResponse]:
    """Return paginated analytics events (admin+)."""
    offset = (page - 1) * limit

    result = await session.execute(
        select(Event)
        .order_by(Event.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    events = result.scalars().all()

    return [
        EventResponse(
            id=e.id,
            user_id=e.user_id,
            event_type=e.event_type,
            url_domain=e.url_domain,
            file_size=e.file_size,
            duration_sec=e.duration_sec,
            processing_ms=e.processing_ms,
            created_at=e.created_at,
        )
        for e in events
    ]
