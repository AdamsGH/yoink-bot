"""Tests for pre-upload postprocessing."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from yoink.download.postprocess import (
    _needs_even_dims,
    _postprocess_sync,
    _probe_streams,
    postprocess,
    _NEEDS_TRANSCODE_VCODEC,
    _TG_VIDEO_CONTAINERS,
)


# -- _needs_even_dims --

def test_even_dims_ok():
    assert _needs_even_dims(1280, 720) is False
    assert _needs_even_dims(640, 480) is False
    assert _needs_even_dims(1920, 1080) is False


def test_odd_width():
    assert _needs_even_dims(641, 480) is True


def test_odd_height():
    assert _needs_even_dims(640, 479) is True


def test_both_odd():
    assert _needs_even_dims(641, 479) is True


# -- codec sets --

def test_vp9_needs_transcode():
    assert "vp9" in _NEEDS_TRANSCODE_VCODEC


def test_av1_needs_transcode():
    assert "av01" in _NEEDS_TRANSCODE_VCODEC
    assert "av1" in _NEEDS_TRANSCODE_VCODEC


def test_mp4_is_tg_container():
    assert ".mp4" in _TG_VIDEO_CONTAINERS


def test_mkv_not_tg_container():
    assert ".mkv" not in _TG_VIDEO_CONTAINERS


def test_webm_not_tg_container():
    assert ".webm" not in _TG_VIDEO_CONTAINERS


# -- passthrough for non-video files --

def test_audio_passthrough(tmp_path):
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"fake mp3")
    result = _postprocess_sync(f)
    assert result == f


def test_image_passthrough(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"fake jpg")
    result = _postprocess_sync(f)
    assert result == f


# -- mp4 with good codec: no changes --

def test_mp4_h264_aac_passthrough(tmp_path):
    f = tmp_path / "video.mp4"
    f.write_bytes(b"fake mp4")

    with patch("yoink.download.postprocess._probe_streams") as mock_probe:
        mock_probe.return_value = ("h264", "aac", 1280, 720, 0)
        result = _postprocess_sync(f)

    assert result == f  # no postprocessing needed


# -- mkv needs remux --

def test_mkv_triggers_remux(tmp_path):
    f = tmp_path / "video.mkv"
    f.write_bytes(b"x" * 1000)
    out = tmp_path / "video.pp.mp4"

    with patch("yoink.download.postprocess._probe_streams") as mock_probe, \
         patch("yoink.download.postprocess._run_ffmpeg") as mock_ffmpeg:
        mock_probe.return_value = ("h264", "aac", 1280, 720, 0)
        # Simulate ffmpeg creating output file
        mock_ffmpeg.side_effect = lambda cmd: (out.write_bytes(b"x" * 900), True)[1]

        result = _postprocess_sync(f)

    assert result == out
    mock_ffmpeg.assert_called_once()
    # Should be a remux (stream copy) command
    cmd = mock_ffmpeg.call_args[0][0]
    assert "-c" in cmd
    assert "copy" in cmd


# -- webm with vp9 needs transcode --

def test_webm_vp9_triggers_transcode(tmp_path):
    f = tmp_path / "video.webm"
    f.write_bytes(b"x" * 1000)
    out = tmp_path / "video.pp.mp4"

    with patch("yoink.download.postprocess._probe_streams") as mock_probe, \
         patch("yoink.download.postprocess._run_ffmpeg") as mock_ffmpeg:
        mock_probe.return_value = ("vp9", "opus", 1280, 720, 0)
        mock_ffmpeg.side_effect = lambda cmd: (out.write_bytes(b"x" * 900), True)[1]

        result = _postprocess_sync(f)

    assert result == out
    cmd = mock_ffmpeg.call_args[0][0]
    assert "libx264" in cmd


# -- odd dimensions trigger scale --

def test_odd_dims_triggers_scale(tmp_path):
    f = tmp_path / "video.mp4"
    f.write_bytes(b"x" * 1000)
    out = tmp_path / "video.pp.mp4"

    with patch("yoink.download.postprocess._probe_streams") as mock_probe, \
         patch("yoink.download.postprocess._run_ffmpeg") as mock_ffmpeg:
        mock_probe.return_value = ("h264", "aac", 641, 480, 0)  # odd width
        mock_ffmpeg.side_effect = lambda cmd: (out.write_bytes(b"x" * 900), True)[1]

        result = _postprocess_sync(f)

    assert result == out
    cmd = mock_ffmpeg.call_args[0][0]
    assert "scale" in " ".join(cmd)


# -- ffmpeg failure falls back to original --

def test_ffmpeg_failure_returns_original(tmp_path):
    f = tmp_path / "video.mkv"
    f.write_bytes(b"x" * 1000)

    with patch("yoink.download.postprocess._probe_streams") as mock_probe, \
         patch("yoink.download.postprocess._run_ffmpeg") as mock_ffmpeg:
        mock_probe.return_value = ("h264", "aac", 1280, 720, 0)
        mock_ffmpeg.return_value = False  # ffmpeg failed

        result = _postprocess_sync(f)

    assert result == f  # original returned on failure


# -- async wrapper --

@pytest.mark.asyncio
async def test_postprocess_async_passthrough(tmp_path):
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"fake")
    result = await postprocess(f)
    assert result == f


@pytest.mark.asyncio
async def test_postprocess_never_raises(tmp_path):
    f = tmp_path / "video.mkv"
    f.write_bytes(b"x" * 100)

    with patch("yoink.download.postprocess._postprocess_sync", side_effect=RuntimeError("boom")):
        result = await postprocess(f)

    assert result == f  # falls back to original, never raises
