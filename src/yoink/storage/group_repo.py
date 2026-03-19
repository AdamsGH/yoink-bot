"""
CRUD repository for Group, ThreadPolicy, UserGroupPolicy.
"""
from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from yoink.storage.models import Group, ThreadPolicy, UserGroupPolicy, UserRole

logger = logging.getLogger(__name__)


class GroupRepo:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    # Group

    async def get(self, group_id: int) -> Group | None:
        async with self._sf() as s:
            return await s.get(Group, group_id)

    async def upsert(
        self,
        group_id: int,
        title: str | None = None,
        auto_grant_role: UserRole = UserRole.user,
        allow_pm: bool = True,
    ) -> Group:
        """Create group if not exists; update title if provided."""
        async with self._sf() as s:
            group = await s.get(Group, group_id)
            if group is None:
                group = Group(
                    id=group_id,
                    title=title,
                    auto_grant_role=auto_grant_role,
                    allow_pm=allow_pm,
                )
                s.add(group)
            else:
                if title is not None:
                    group.title = title
            await s.commit()
            await s.refresh(group)
            return group

    async def update(
        self,
        group_id: int,
        enabled: bool | None = None,
        auto_grant_role: UserRole | None = None,
        allow_pm: bool | None = None,
        nsfw_allowed: bool | None = None,
    ) -> Group | None:
        async with self._sf() as s:
            group = await s.get(Group, group_id)
            if group is None:
                return None
            if enabled is not None:
                group.enabled = enabled
            if auto_grant_role is not None:
                group.auto_grant_role = auto_grant_role
            if allow_pm is not None:
                group.allow_pm = allow_pm
            if nsfw_allowed is not None:
                group.nsfw_allowed = nsfw_allowed
            await s.commit()
            await s.refresh(group)
            return group

    async def is_enabled(self, group_id: int) -> bool:
        group = await self.get(group_id)
        return group is not None and group.enabled

    async def delete(self, group_id: int) -> bool:
        async with self._sf() as s:
            group = await s.get(Group, group_id)
            if group is None:
                return False
            await s.delete(group)
            await s.commit()
            return True

    async def list_all(self) -> Sequence[Group]:
        async with self._sf() as s:
            result = await s.execute(select(Group).order_by(Group.id))
            return result.scalars().all()

    # ThreadPolicy

    async def get_thread_policy(
        self, group_id: int, thread_id: int | None
    ) -> ThreadPolicy | None:
        async with self._sf() as s:
            stmt = select(ThreadPolicy).where(
                ThreadPolicy.group_id == group_id,
                ThreadPolicy.thread_id == thread_id,
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def set_thread_policy(
        self, group_id: int, thread_id: int | None, enabled: bool
    ) -> ThreadPolicy:
        async with self._sf() as s:
            stmt = select(ThreadPolicy).where(
                ThreadPolicy.group_id == group_id,
                ThreadPolicy.thread_id == thread_id,
            )
            result = await s.execute(stmt)
            policy = result.scalar_one_or_none()
            if policy is None:
                policy = ThreadPolicy(
                    group_id=group_id,
                    thread_id=thread_id,
                    enabled=enabled,
                )
                s.add(policy)
            else:
                policy.enabled = enabled
            await s.commit()
            await s.refresh(policy)
            return policy

    async def upsert_thread_name(
        self, group_id: int, thread_id: int, name: str
    ) -> None:
        """Record a forum topic name from a service message.

        Creates the ThreadPolicy row if it doesn't exist yet (enabled=True by
        default  - just discovering the topic, not restricting it). Only updates
        the name if the row already exists, leaving enabled unchanged.
        """
        async with self._sf() as s:
            stmt = select(ThreadPolicy).where(
                ThreadPolicy.group_id == group_id,
                ThreadPolicy.thread_id == thread_id,
            )
            result = await s.execute(stmt)
            policy = result.scalar_one_or_none()
            if policy is None:
                policy = ThreadPolicy(
                    group_id=group_id,
                    thread_id=thread_id,
                    name=name,
                    enabled=True,
                )
                s.add(policy)
            else:
                policy.name = name
            await s.commit()

    async def delete_thread_policy(
        self, group_id: int, thread_id: int | None
    ) -> bool:
        async with self._sf() as s:
            stmt = delete(ThreadPolicy).where(
                ThreadPolicy.group_id == group_id,
                ThreadPolicy.thread_id == thread_id,
            )
            result = await s.execute(stmt)
            await s.commit()
            return result.rowcount > 0

    async def list_thread_policies(self, group_id: int) -> Sequence[ThreadPolicy]:
        async with self._sf() as s:
            result = await s.execute(
                select(ThreadPolicy).where(ThreadPolicy.group_id == group_id)
            )
            return result.scalars().all()

    # ThreadPolicy check

    async def is_thread_allowed(
        self, group_id: int, thread_id: int | None
    ) -> bool:
        """
        Return True if the bot should process requests in this thread.

        Logic:
        - If no Group row exists → deny.
        - If ThreadPolicy row exists for this exact thread → use its enabled flag.
        - Otherwise check the mode inferred from existing policies:
            Blacklist mode (default): no enabled=True policies exist →
              threads without a policy are allowed.
            Whitelist mode: at least one enabled=True policy exists →
              threads without a policy are denied (must be explicitly listed).
        """
        group = await self.get(group_id)
        if group is None:
            return False

        policy = await self.get_thread_policy(group_id, thread_id)
        if policy is not None:
            return policy.enabled

        # Determine mode from existing policies
        all_policies = await self.list_thread_policies(group_id)
        has_whitelist = any(p.enabled for p in all_policies)
        if has_whitelist:
            # Whitelist mode: unlisted threads are denied
            return False

        # Blacklist mode: unlisted threads are allowed
        return True

    # UserGroupPolicy

    async def get_user_policy(
        self, user_id: int, group_id: int
    ) -> UserGroupPolicy | None:
        async with self._sf() as s:
            stmt = select(UserGroupPolicy).where(
                UserGroupPolicy.user_id == user_id,
                UserGroupPolicy.group_id == group_id,
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def set_user_policy(
        self,
        user_id: int,
        group_id: int,
        role_override: UserRole | None = None,
        allow_pm_override: bool | None = None,
    ) -> UserGroupPolicy:
        async with self._sf() as s:
            stmt = select(UserGroupPolicy).where(
                UserGroupPolicy.user_id == user_id,
                UserGroupPolicy.group_id == group_id,
            )
            result = await s.execute(stmt)
            policy = result.scalar_one_or_none()
            if policy is None:
                policy = UserGroupPolicy(
                    user_id=user_id,
                    group_id=group_id,
                    role_override=role_override,
                    allow_pm_override=allow_pm_override,
                )
                s.add(policy)
            else:
                if role_override is not None:
                    policy.role_override = role_override
                if allow_pm_override is not None:
                    policy.allow_pm_override = allow_pm_override
            await s.commit()
            await s.refresh(policy)
            return policy
