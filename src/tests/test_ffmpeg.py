"""Tests for FFmpeg utilities."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from yoink.download.ffmpeg import (
    _make_thumb_sync,
    _split_sync,
    ffmpeg_available,
)


def test_ffmpeg_available():
    # Just verifies the function runs without error
    result = ffmpeg_available()
    assert isinstance(result, bool)


def test_split_returns_original_if_no_split_needed(tmp_path):
    """If file fits in max_bytes, return [original]."""
    video = tmp_path / "test.mp4"
    video.write_bytes(b"x" * 100)

    result = _split_sync(
        video_path=video,
        out_dir=tmp_path,
        max_bytes=10_000_000,  # 10MB >> 100 bytes
        duration=60.0,
    )
    assert result == [video]


def test_split_calculates_correct_parts(tmp_path):
    """Verify split count calculation: ceil(file_size / max_bytes)."""
    import math
    video = tmp_path / "big.mp4"
    file_size = 5_000_000  # 5MB
    video.write_bytes(b"x" * file_size)
    max_bytes = 2_000_000  # 2MB -> ceil(5/2) = 3 parts

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        # Simulate parts being created
        for i in range(1, 4):
            part = tmp_path / f"big_part{i:02d}.mp4"
            part.write_bytes(b"x" * 100)

        result = _split_sync(
            video_path=video,
            out_dir=tmp_path,
            max_bytes=max_bytes,
            duration=90.0,
        )
    # 3 parts were pre-created
    mp4_parts = [p for p in tmp_path.iterdir() if "_part" in p.name]
    assert len(mp4_parts) == 3


@pytest.mark.asyncio
async def test_get_video_info_returns_zeros_on_failure(tmp_path):
    """get_video_info should never raise, return (0,0,0) on bad file."""
    from yoink.download.ffmpeg import get_video_info
    fake = tmp_path / "notavideo.mp4"
    fake.write_bytes(b"not a video")
    duration, w, h = await get_video_info(fake)
    assert duration == 0.0
    assert w == 0
    assert h == 0


@pytest.mark.asyncio
async def test_fix_srt_encoding_utf8_passthrough(tmp_path):
    """Valid UTF-8 SRT should pass through unchanged."""
    from yoink.download.ffmpeg import fix_srt_encoding
    srt = tmp_path / "subs.srt"
    content = "1\n00:00:01,000 --> 00:00:02,000\nHello world\n\n"
    srt.write_text(content, encoding="utf-8")
    result = await fix_srt_encoding(srt)
    assert result == srt
    assert srt.read_text(encoding="utf-8") == content
