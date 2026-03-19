"""Cookie management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.api.deps import get_current_user, get_db, require_role
from yoink.api.schemas import CookieListResponse, CookieResponse, CookieUploadRequest
from yoink.services.cookies import validate_netscape
from yoink.storage.models import Cookie, User, UserRole

router = APIRouter(prefix="/cookies", tags=["cookies"])

_ADMIN_ROLES = (UserRole.owner, UserRole.admin)


def _cookie_to_response(c: Cookie) -> CookieResponse:
    return CookieResponse(
        id=c.id,
        user_id=c.user_id,
        domain=c.domain,
        is_valid=c.is_valid,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=CookieListResponse)
async def list_my_cookies(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CookieListResponse:
    """List cookies belonging to the authenticated user."""
    result = await session.execute(
        select(Cookie).where(Cookie.user_id == current_user.id).order_by(Cookie.domain)
    )
    cookies = result.scalars().all()
    return CookieListResponse(items=[_cookie_to_response(c) for c in cookies])


@router.post("", response_model=CookieResponse, status_code=status.HTTP_201_CREATED)
async def upload_cookie(
    body: CookieUploadRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CookieResponse:
    """Upload or replace a cookie. Users may only upload for themselves; admins for any user."""
    if body.user_id != current_user.id and current_user.role not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only upload cookies for your own account",
        )

    if not validate_netscape(body.content):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Content does not appear to be a valid Netscape cookie file",
        )

    result = await session.execute(
        select(Cookie).where(Cookie.user_id == body.user_id, Cookie.domain == body.domain)
    )
    cookie = result.scalar_one_or_none()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    if cookie is None:
        # Ensure user exists
        target_user = await session.get(User, body.user_id)
        if target_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")
        cookie = Cookie(
            user_id=body.user_id,
            domain=body.domain,
            content=body.content,
            is_valid=True,
        )
        session.add(cookie)
    else:
        cookie.content = body.content
        cookie.is_valid = True
        cookie.updated_at = now

    await session.commit()
    await session.refresh(cookie)
    return _cookie_to_response(cookie)


@router.delete("/{domain}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_cookie(
    domain: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a cookie by domain. Users delete their own; admins may use /cookies/all path."""
    from sqlalchemy import delete as sa_delete

    result = await session.execute(
        sa_delete(Cookie)
        .where(Cookie.user_id == current_user.id, Cookie.domain == domain)
        .returning(Cookie.id)
    )
    await session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cookie not found")


@router.get("/all", response_model=CookieListResponse)
async def list_all_cookies(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> CookieListResponse:
    """List all cookies across all users (admin+)."""
    result = await session.execute(
        select(Cookie).order_by(Cookie.user_id, Cookie.domain)
    )
    cookies = result.scalars().all()
    return CookieListResponse(items=[_cookie_to_response(c) for c in cookies])
