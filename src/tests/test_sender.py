"""Tests for upload sender logic."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path

from telegram.error import RetryAfter

from yoink.upload.sender import (
    _caption_fallbacks,
    _retry,
    MediaMeta,
    SendResult,
)


# -- caption fallbacks --

def test_caption_fallbacks_short():
    caps = _caption_fallbacks("Hello")
    assert caps == ["Hello"]


def test_caption_fallbacks_long():
    long = "x" * 2000
    caps = _caption_fallbacks(long)
    assert len(caps) == 2
    assert len(caps[0]) == 2000
    assert len(caps[1]) <= 1024
    assert caps[1].endswith("…")


# -- retry logic --

@pytest.mark.asyncio
async def test_retry_succeeds_on_first_try():
    sender = AsyncMock(return_value=MagicMock())
    result = await _retry(sender, "cap", fallback=None)
    assert result is not None
    sender.assert_called_once_with("cap")


@pytest.mark.asyncio
async def test_retry_on_flood_wait():
    """Should sleep and retry after RetryAfter."""
    flood = RetryAfter(retry_after=1)
    ok_msg = MagicMock()
    sender = AsyncMock(side_effect=[flood, ok_msg])

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await _retry(sender, "cap", fallback=None)

    assert result is ok_msg
    mock_sleep.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_retry_exhausts_flood_returns_none():
    """After max RetryAfter retries, should return None."""
    flood = RetryAfter(retry_after=1)
    sender = AsyncMock(side_effect=[flood, flood, flood, flood])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await _retry(
            sender, "cap", fallback=None, max_flood=3
        )
    assert result is None


@pytest.mark.asyncio
async def test_retry_timeout_falls_back_to_document():
    """On timeout, should fall back to document sender."""
    timeout_err = TimeoutError("Request timed out")
    doc_msg = MagicMock()
    sender = AsyncMock(side_effect=timeout_err)
    fallback = AsyncMock(return_value=doc_msg)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await _retry(
            sender, "cap", fallback=fallback, max_timeout=1
        )
    assert result is doc_msg
    fallback.assert_called_once_with("cap")


@pytest.mark.asyncio
async def test_media_caption_too_long_re_raises():
    """MEDIA_CAPTION_TOO_LONG should propagate to trigger caption fallback."""
    err = Exception("MEDIA_CAPTION_TOO_LONG: caption too long")
    sender = AsyncMock(side_effect=err)

    with pytest.raises(Exception, match="MEDIA_CAPTION_TOO_LONG"):
        await _retry(sender, "cap", fallback=None)
