"""Tests for per-user settings storage."""
from __future__ import annotations

import pytest
from yoink.storage.user_settings import UserSettingsRepo


@pytest.mark.asyncio
async def test_get_creates_defaults(session_factory):
    repo = UserSettingsRepo(session_factory)
    s = await repo.get(123)
    assert s.user_id == 123
    assert s.language == "en"
    assert s.quality == "best"
    assert s.proxy_enabled is False


@pytest.mark.asyncio
async def test_update_language(session_factory):
    repo = UserSettingsRepo(session_factory)
    await repo.set_language(456, "ru")
    s = await repo.get(456)
    assert s.language == "ru"


@pytest.mark.asyncio
async def test_update_multiple_fields(session_factory):
    repo = UserSettingsRepo(session_factory)
    await repo.update(789, quality="720", codec="av01", container="mkv")
    s = await repo.get(789)
    assert s.quality == "720"
    assert s.codec == "av01"
    assert s.container == "mkv"


@pytest.mark.asyncio
async def test_toggle_proxy(session_factory):
    repo = UserSettingsRepo(session_factory)
    await repo.toggle_proxy(111, True)
    s = await repo.get(111)
    assert s.proxy_enabled is True

    await repo.toggle_proxy(111, False)
    s = await repo.get(111)
    assert s.proxy_enabled is False


@pytest.mark.asyncio
async def test_set_args(session_factory):
    repo = UserSettingsRepo(session_factory)
    args = {"geo_bypass": True, "retries": 5}
    await repo.set_args(222, args)
    s = await repo.get(222)
    assert s.args_json == args


@pytest.mark.asyncio
async def test_block_user(session_factory):
    repo = UserSettingsRepo(session_factory)
    assert await repo.is_blocked(333) is False
    await repo.update(333, blocked=True)
    assert await repo.is_blocked(333) is True


@pytest.mark.asyncio
async def test_second_get_returns_same_defaults(session_factory):
    repo = UserSettingsRepo(session_factory)
    s1 = await repo.get(999)
    s2 = await repo.get(999)
    assert s1.language == s2.language
    assert s1.quality == s2.quality
