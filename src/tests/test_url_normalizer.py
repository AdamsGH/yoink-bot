"""Tests for URL normalization."""
from __future__ import annotations

import pytest
from yoink.url.normalizer import (
    normalize,
    normalize_for_cache,
    extract_range,
    is_playlist_url,
    _resolve_google_redirect,
    _strip_tracking_params,
)
from yoink.url.domains import DomainConfig


@pytest.fixture
def domain_cfg():
    return DomainConfig()


# -- extract_range --

def test_extract_range_basic():
    url, start, end = extract_range("https://youtube.com/playlist?list=PL*1*5")
    assert url == "https://youtube.com/playlist?list=PL"
    assert start == 1
    assert end == 5


def test_extract_range_negative():
    url, start, end = extract_range("https://tiktok.com/@user*-1*-10")
    assert start == -1
    assert end == -10


def test_extract_range_no_range():
    url, start, end = extract_range("https://youtube.com/watch?v=abc")
    assert url == "https://youtube.com/watch?v=abc"
    assert start is None
    assert end is None


def test_is_playlist_url_true():
    assert is_playlist_url("https://x.com/playlist*1*5") is True


def test_is_playlist_url_false():
    assert is_playlist_url("https://youtube.com/watch?v=abc") is False


# -- Google redirect --

def test_resolve_google_redirect():
    url = "https://www.google.com/url?q=https%3A%2F%2Fyoutube.com%2Fwatch%3Fv%3Dabc&sa=D"
    result = _resolve_google_redirect(url)
    assert "youtube.com" in result
    assert "google.com" not in result


def test_resolve_non_google():
    url = "https://youtube.com/watch?v=abc"
    assert _resolve_google_redirect(url) == url


# -- tracking params --

def test_strip_utm_params():
    url = "https://example.com/video?v=123&utm_source=twitter&utm_medium=social"
    result = _strip_tracking_params(url)
    assert "utm_source" not in result
    assert "utm_medium" not in result
    assert "v=123" in result


def test_strip_fbclid():
    url = "https://example.com/vid?id=1&fbclid=ABC123"
    result = _strip_tracking_params(url)
    assert "fbclid" not in result
    assert "id=1" in result


# -- normalize_for_cache --

def test_cache_youtube_watch(domain_cfg):
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&utm_source=share&list=PL123"
    result = normalize_for_cache(url, domain_cfg)
    assert result == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_cache_youtube_shorts(domain_cfg):
    url = "https://www.youtube.com/shorts/abcdef?feature=share"
    result = normalize_for_cache(url, domain_cfg)
    assert "feature" not in result
    assert "shorts/abcdef" in result


def test_cache_youtu_be(domain_cfg):
    url = "https://youtu.be/dQw4w9WgXcQ?si=XXXXXXXX"
    result = normalize_for_cache(url, domain_cfg)
    assert "si=" not in result
    assert "dQw4w9WgXcQ" in result


def test_cache_tiktok_strips_params(domain_cfg):
    url = "https://www.tiktok.com/@user/video/123456?lang=en"
    result = normalize_for_cache(url, domain_cfg)
    assert "lang=" not in result


def test_cache_strips_range_tags(domain_cfg):
    url = "https://youtube.com/playlist?list=PL*1*5"
    result = normalize_for_cache(url, domain_cfg)
    assert "*1*5" not in result
