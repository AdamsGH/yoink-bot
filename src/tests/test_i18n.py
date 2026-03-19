"""Tests for i18n loader."""
from __future__ import annotations

import pytest
from yoink.i18n.loader import t, clear_cache


def setup_function():
    clear_cache()


def test_existing_key():
    result = t("common.done", "en")
    assert result == "Done."


def test_missing_key_returns_placeholder():
    result = t("nonexistent.key.here", "en")
    assert result == "[nonexistent.key.here]"


def test_interpolation():
    result = t("common.flood_wait", "en", seconds=30)
    assert "30" in result


def test_missing_interpolation_variable_is_safe():
    # Should not raise - missing vars become {var}
    result = t("download.error", "en")
    assert "[" not in result or "error" in result


def test_unknown_lang_falls_back_to_en():
    result = t("common.done", "xx_unknown")
    assert result == "Done."


def test_nested_key():
    result = t("format.buttons.best", "en")
    assert result != "[format.buttons.best]"
