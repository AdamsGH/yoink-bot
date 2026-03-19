"""
Auto-discovery of command modules.

Each module must expose: register(app: Application) -> None
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path

from telegram.ext import Application

logger = logging.getLogger(__name__)


def register_all(app: Application) -> None:
    pkg_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(pkg_dir)]):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"yoink.commands.{module_info.name}")
        if hasattr(module, "register"):
            module.register(app)
            logger.debug("Registered command module: %s", module_info.name)
