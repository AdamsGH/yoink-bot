"""User management endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.api.deps import get_current_user, get_db, require_role
from yoink.api.schemas import UserListResponse, UserResponse, UserUpdateRequest
from yoink.storage.models import DownloadLog, User, UserRole

router = APIRouter(prefix="/users", tags=["users"])

_ADMIN_ROLES = (UserRole.owner, UserRole.admin)


class UserStatsResponse(BaseModel):
    total: int
    this_week: int
    today: int
    top_domains: list[dict]
    member_since: datetime


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_my_stats(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserStatsResponse:
    """Personal download statistics for the authenticated user."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    base = DownloadLog.user_id == current_user.id

    total = (await session.execute(
        select(func.count()).select_from(DownloadLog).where(base)
    )).scalar_one()

    today = (await session.execute(
        select(func.count()).select_from(DownloadLog)
        .where(base, DownloadLog.created_at >= today_start)
    )).scalar_one()

    this_week = (await session.execute(
        select(func.count()).select_from(DownloadLog)
        .where(base, DownloadLog.created_at >= week_start)
    )).scalar_one()

    top_result = await session.execute(
        select(DownloadLog.domain, func.count().label("count"))
        .where(base, DownloadLog.domain.isnot(None))
        .group_by(DownloadLog.domain)
        .order_by(func.count().desc())
        .limit(5)
    )
    top_domains = [{"domain": r.domain, "count": r.count} for r in top_result]

    return UserStatsResponse(
        total=total,
        today=today,
        this_week=this_week,
        top_domains=top_domains,
        member_since=current_user.created_at,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's info."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        first_name=current_user.first_name,
        role=current_user.role,
        created_at=current_user.created_at,
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    limit: int = 20,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> UserListResponse:
    """List all users (admin+)."""
    offset = (page - 1) * limit

    total_result = await session.execute(select(func.count()).select_from(User))
    total = total_result.scalar_one()

    result = await session.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    users = result.scalars().all()

    return UserListResponse(
        items=[
            UserResponse(
                id=u.id,
                username=u.username,
                first_name=u.first_name,
                role=u.role,
                created_at=u.created_at,
            )
            for u in users
        ],
        total=total,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> UserResponse:
    """Get a specific user by ID (admin+)."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        role=user.role,
        created_at=user.created_at,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> UserResponse:
    """Update a user's role or ban_until (admin+)."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.role is not None:
        user.role = body.role
    if body.ban_until is not None:
        user.ban_until = body.ban_until

    user.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        role=user.role,
        created_at=user.created_at,
    )
