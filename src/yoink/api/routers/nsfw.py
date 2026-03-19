"""NSFW domain and keyword management API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from yoink.api.deps import get_db, require_role
from yoink.storage.models import NsfwDomain, NsfwKeyword, User, UserRole
from yoink.api.schemas import (
    NsfwDomainCreateRequest, NsfwDomainListResponse, NsfwDomainResponse,
    NsfwKeywordCreateRequest, NsfwKeywordListResponse, NsfwKeywordResponse,
    NsfwCheckRequest, NsfwCheckResponse,
)

router = APIRouter(prefix="/nsfw", tags=["nsfw"])

_ADMIN_ROLES = (UserRole.owner, UserRole.admin)


# Domains

@router.get("/domains", response_model=NsfwDomainListResponse)
async def list_domains(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> NsfwDomainListResponse:
    rows = (await session.execute(select(NsfwDomain).order_by(NsfwDomain.domain))).scalars().all()
    items = [NsfwDomainResponse(id=r.id, domain=r.domain, note=r.note, created_at=r.created_at) for r in rows]
    return NsfwDomainListResponse(items=items, total=len(items))


@router.post("/domains", response_model=NsfwDomainResponse, status_code=status.HTTP_201_CREATED)
async def add_domain(
    body: NsfwDomainCreateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> NsfwDomainResponse:
    domain = body.domain.lower().removeprefix("www.")
    existing = (await session.execute(
        select(NsfwDomain).where(NsfwDomain.domain == domain)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Domain already exists")
    row = NsfwDomain(domain=domain, note=body.note)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await _reload_checker(session)
    return NsfwDomainResponse(id=row.id, domain=row.domain, note=row.note, created_at=row.created_at)


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(
    domain_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> None:
    row = await session.get(NsfwDomain, domain_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    await session.delete(row)
    await session.commit()
    await _reload_checker(session)


# Keywords

@router.get("/keywords", response_model=NsfwKeywordListResponse)
async def list_keywords(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> NsfwKeywordListResponse:
    rows = (await session.execute(select(NsfwKeyword).order_by(NsfwKeyword.keyword))).scalars().all()
    items = [NsfwKeywordResponse(id=r.id, keyword=r.keyword, note=r.note, created_at=r.created_at) for r in rows]
    return NsfwKeywordListResponse(items=items, total=len(items))


@router.post("/keywords", response_model=NsfwKeywordResponse, status_code=status.HTTP_201_CREATED)
async def add_keyword(
    body: NsfwKeywordCreateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> NsfwKeywordResponse:
    keyword = body.keyword.lower()
    existing = (await session.execute(
        select(NsfwKeyword).where(NsfwKeyword.keyword == keyword)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Keyword already exists")
    row = NsfwKeyword(keyword=keyword, note=body.note)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await _reload_checker(session)
    return NsfwKeywordResponse(id=row.id, keyword=row.keyword, note=row.note, created_at=row.created_at)


@router.delete("/keywords/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    keyword_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> None:
    row = await session.get(NsfwKeyword, keyword_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    await session.delete(row)
    await session.commit()
    await _reload_checker(session)


# Check

@router.post("/check", response_model=NsfwCheckResponse)
async def check_url(
    body: NsfwCheckRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> NsfwCheckResponse:
    """Debug endpoint: run NSFW detection against a URL + metadata."""
    from yoink.services.nsfw import NsfwChecker
    from sqlalchemy.ext.asyncio import async_sessionmaker
    sf: async_sessionmaker = session.get_bind()  # type: ignore[assignment]
    checker = NsfwChecker(sf)
    await checker.load()
    info = {"title": body.title, "description": body.description, "tags": body.tags}
    is_nsfw, reason = checker.check(body.url, info=info)
    return NsfwCheckResponse(is_nsfw=is_nsfw, reason=reason)


# Helpers

async def _reload_checker(session: AsyncSession) -> None:
    """No-op in API process - bot reloads on next startup or via /nsfw reload."""
    pass
