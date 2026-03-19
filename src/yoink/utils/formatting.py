"""Human-readable formatting utilities."""
from __future__ import annotations

import math


def humanbytes(size: int | float) -> str:
    """Convert bytes to human-readable string: 1536 -> '1.5 KB'"""
    if size == 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    i = int(math.log(size, 1024))
    i = min(i, len(units) - 1)
    value = size / (1024 ** i)
    if i == 0:
        return f"{int(value)} B"
    return f"{value:.1f} {units[i]}"


def humantime(milliseconds: int | float) -> str:
    """Convert ms to human-readable duration: 3723000 -> '1h 2m 3s'"""
    seconds = int(milliseconds / 1000)
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m {sec}s"


format_size = humanbytes  # alias for readability


def progress_bar(current: int, total: int, width: int = 10) -> str:
    """Return a text progress bar: ████████░░ 80%"""
    if total <= 0:
        return "░" * width + " 0%"
    ratio = min(current / total, 1.0)
    filled = int(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {ratio * 100:.0f}%"
