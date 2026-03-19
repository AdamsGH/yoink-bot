"""Group and group policy management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yoink.api.deps import get_db, require_role
from yoink.api.schemas import (
    GroupCreateRequest,
    GroupListResponse,
    GroupResponse,
    GroupUpdateRequest,
    ThreadPolicyRequest,
    ThreadPolicyResponse,
    UserGroupPolicyRequest,
    UserGroupPolicyResponse,
)
from yoink.storage.models import Group, ThreadPolicy, User, UserGroupPolicy, UserRole

router = APIRouter(prefix="/groups", tags=["groups"])

_ADMIN_ROLES = (UserRole.owner, UserRole.admin)


def _group_to_response(g: Group) -> GroupResponse:
    return GroupResponse(
        id=g.id,
        title=g.title,
        enabled=g.enabled,
        auto_grant_role=g.auto_grant_role,
        allow_pm=g.allow_pm,
        nsfw_allowed=g.nsfw_allowed,
        created_at=g.created_at,
    )


# Groups CRUD

@router.get("", response_model=GroupListResponse)
async def list_groups(
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> GroupListResponse:
    result = await session.execute(select(Group).order_by(Group.id))
    items = [_group_to_response(g) for g in result.scalars().all()]
    return GroupListResponse(items=items, total=len(items))


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> GroupResponse:
    existing = await session.get(Group, body.id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Group already exists")

    group = Group(
        id=body.id,
        title=body.title,
        auto_grant_role=body.auto_grant_role,
        allow_pm=body.allow_pm,
        nsfw_allowed=body.nsfw_allowed,
    )
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return _group_to_response(group)


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> GroupResponse:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return _group_to_response(group)


@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    body: GroupUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> GroupResponse:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    if body.title is not None:
        group.title = body.title
    if body.enabled is not None:
        group.enabled = body.enabled
    if body.auto_grant_role is not None:
        group.auto_grant_role = body.auto_grant_role
    if body.allow_pm is not None:
        group.allow_pm = body.allow_pm
    if body.nsfw_allowed is not None:
        group.nsfw_allowed = body.nsfw_allowed

    await session.commit()
    await session.refresh(group)
    return _group_to_response(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> None:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    await session.delete(group)
    await session.commit()


# Thread policies

@router.get("/{group_id}/threads", response_model=list[ThreadPolicyResponse])
async def list_thread_policies(
    group_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> list[ThreadPolicyResponse]:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    result = await session.execute(
        select(ThreadPolicy).where(ThreadPolicy.group_id == group_id)
    )
    policies = result.scalars().all()
    return [
        ThreadPolicyResponse(
            id=p.id,
            group_id=p.group_id,
            thread_id=p.thread_id,
            name=p.name,
            enabled=p.enabled,
        )
        for p in policies
    ]


@router.post(
    "/{group_id}/threads",
    response_model=ThreadPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_thread_policy(
    group_id: int,
    body: ThreadPolicyRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> ThreadPolicyResponse:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    result = await session.execute(
        select(ThreadPolicy).where(
            ThreadPolicy.group_id == group_id,
            ThreadPolicy.thread_id == body.thread_id,
        )
    )
    policy = result.scalar_one_or_none()

    if policy is None:
        policy = ThreadPolicy(
            group_id=group_id,
            thread_id=body.thread_id,
            name=body.name,
            enabled=body.enabled,
        )
        session.add(policy)
    else:
        policy.enabled = body.enabled
        if body.name is not None:
            policy.name = body.name

    await session.commit()
    await session.refresh(policy)
    return ThreadPolicyResponse(
        id=policy.id,
        group_id=policy.group_id,
        thread_id=policy.thread_id,
        name=policy.name,
        enabled=policy.enabled,
    )


@router.delete("/{group_id}/threads/{thread_policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread_policy(
    group_id: int,
    thread_policy_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> None:
    policy = await session.get(ThreadPolicy, thread_policy_id)
    if policy is None or policy.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread policy not found")
    await session.delete(policy)
    await session.commit()


# User overrides

@router.get("/{group_id}/members", response_model=list[UserGroupPolicyResponse])
async def list_member_overrides(
    group_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> list[UserGroupPolicyResponse]:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    result = await session.execute(
        select(UserGroupPolicy).where(UserGroupPolicy.group_id == group_id)
    )
    policies = result.scalars().all()
    return [
        UserGroupPolicyResponse(
            user_id=p.user_id,
            group_id=p.group_id,
            role_override=p.role_override,
            allow_pm_override=p.allow_pm_override,
        )
        for p in policies
    ]


@router.put("/{group_id}/members/{user_id}", response_model=UserGroupPolicyResponse)
async def set_member_override(
    group_id: int,
    user_id: int,
    body: UserGroupPolicyRequest,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> UserGroupPolicyResponse:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    result = await session.execute(
        select(UserGroupPolicy).where(
            UserGroupPolicy.user_id == user_id,
            UserGroupPolicy.group_id == group_id,
        )
    )
    policy = result.scalar_one_or_none()

    if policy is None:
        # Ensure user exists
        target_user = await session.get(User, user_id)
        if target_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        policy = UserGroupPolicy(
            user_id=user_id,
            group_id=group_id,
            role_override=body.role_override,
            allow_pm_override=body.allow_pm_override,
        )
        session.add(policy)
    else:
        policy.role_override = body.role_override
        policy.allow_pm_override = body.allow_pm_override

    await session.commit()
    await session.refresh(policy)
    return UserGroupPolicyResponse(
        user_id=policy.user_id,
        group_id=policy.group_id,
        role_override=policy.role_override,
        allow_pm_override=policy.allow_pm_override,
    )


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_override(
    group_id: int,
    user_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(*_ADMIN_ROLES)),
) -> None:
    result = await session.execute(
        select(UserGroupPolicy).where(
            UserGroupPolicy.user_id == user_id,
            UserGroupPolicy.group_id == group_id,
        )
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")
    await session.delete(policy)
    await session.commit()
