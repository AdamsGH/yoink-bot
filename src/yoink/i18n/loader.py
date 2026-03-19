"""i18n loader. Keys are dot-separated: t('download.starting', 'ru')."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LANG = "en"
SUPPORTED = {"en", "ru", "ar", "hi", "zh", "ja"}


@lru_cache(maxsize=16)
def _load(lang: str) -> dict[str, Any]:
    path = LOCALES_DIR / f"{lang}.yml"
    if not path.exists():
        if lang != DEFAULT_LANG:
            logger.warning("Locale '%s' not found, falling back to '%s'", lang, DEFAULT_LANG)
            return _load(DEFAULT_LANG)
        raise FileNotFoundError(f"Default locale file missing: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve(data: dict[str, Any], key: str) -> Any:
    """Walk a dot-separated key through nested dicts."""
    node: Any = data
    for part in key.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def t(key: str, lang: str = DEFAULT_LANG, **kwargs: Any) -> str:
    """
    Translate a dot-separated key for the given language.
    Falls back to DEFAULT_LANG if key missing in requested language.
    Returns '[key]' placeholder if missing in both.
    """
    data = _load(lang if lang in SUPPORTED else DEFAULT_LANG)
    value = _resolve(data, key)

    if value is None and lang != DEFAULT_LANG:
        # Try English fallback
        value = _resolve(_load(DEFAULT_LANG), key)

    if value is None:
        logger.debug("Missing i18n key: '%s' (lang=%s)", key, lang)
        return f"[{key}]"

    if not isinstance(value, str):
        return str(value)

    if kwargs:
        try:
            return value.format_map(_SafeDict(kwargs))
        except Exception:
            return value

    return value


class _SafeDict(dict):  # type: ignore[type-arg]
    """dict that returns '{key}' for missing keys instead of raising KeyError."""
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


def clear_cache() -> None:
    _load.cache_clear()
