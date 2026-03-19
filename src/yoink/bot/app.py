"""
Application factory.
"""
from __future__ import annotations

import httpx
from telegram.ext import Application
from telegram.request import HTTPXRequest

from yoink.config.settings import Settings


def create_app(settings: Settings) -> Application:
    # Explicit httpx timeout so polling never hangs forever on a dead connection.
    # connect: TCP handshake; read: long-poll window + margin; write/pool: generous.
    request = HTTPXRequest(
        http_version="1.1",
        connection_pool_size=8,
        httpx_kwargs={
            "timeout": httpx.Timeout(
                connect=10.0,
                read=30.0,
                write=60.0,
                pool=5.0,
            ),
        },
    )

    builder = (
        Application.builder()
        .token(settings.bot_token)
        .request(request)
    )
    if settings.telegram_base_url != "https://api.telegram.org/bot":
        builder = builder.base_url(settings.telegram_base_url)
    return builder.build()
