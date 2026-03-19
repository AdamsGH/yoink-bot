"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from yoink.api.routers import auth, bot_settings, cookies, downloads, groups, nsfw, settings, stats, users
from yoink.config.settings import load_settings
from yoink.storage.db import create_tables, init_engine, get_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    cfg = load_settings()
    init_engine(cfg.database_url, echo=cfg.database_echo)
    await create_tables()
    app.state.settings = cfg
    app.state.session_factory = get_session_factory()
    yield


app = FastAPI(
    title="Yoink API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(downloads.router, prefix="/api/v1")
app.include_router(cookies.router, prefix="/api/v1")
app.include_router(groups.router, prefix="/api/v1")
app.include_router(nsfw.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(bot_settings.router, prefix="/api/v1")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/docs", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(openapi_url="/openapi.json", title="Yoink API")


def main() -> None:
    cfg = load_settings()
    uvicorn.run(
        "yoink.api.main:app",
        host="0.0.0.0",
        port=cfg.api_port,
        reload=cfg.debug,
    )
