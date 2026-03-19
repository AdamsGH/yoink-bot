# yoink (Python package)

Core package for both the Telegram bot and the FastAPI service.
Two CLI entrypoints share all models, storage, and business logic.

```
yoink-bot  ->  yoink.main:main       PTB bot process
yoink-api  ->  yoink.api.main:main   FastAPI / uvicorn process
```

## Package layout

```
yoink/
  api/              - FastAPI application
    routers/        - one file per resource (auth, users, settings, downloads, ...)
    schemas.py      - Pydantic request/response models
    deps.py         - FastAPI dependencies (get_db, get_current_user, require_role)
    auth.py         - JWT encode/decode
    main.py         - app factory, router registration, lifespan
  bot/              - PTB application wiring
    app.py          - build_application(), middleware registration
    bot_commands.py - BotCommand scopes by role (default, groups, per-user)
    middleware.py   - UserSettingsMiddleware injecting settings into context
  commands/         - one file per bot command, each exposes register(app)
  config/
    settings.py     - Pydantic BaseSettings, all values from environment
  download/
    manager.py      - engine routing (ytdlp / gallery_dl / ytdlp_then_gallery)
    ytdlp.py        - yt-dlp async wrapper, option builder
    gallery.py      - gallery-dl async wrapper
    postprocess.py  - ffmpeg clip cutting, audio extraction
  i18n/
    loader.py       - YAML locale loader
    locales/        - en.yml (and future locales)
  services/
    cookies.py      - CookieManager: per-user Netscape cookies + browser profile
    nsfw.py         - NsfwChecker: domain list, URL keywords, metadata keywords
    proxy.py        - proxy URL helpers
  storage/
    models.py       - SQLAlchemy ORM models (User, Group, DownloadLog, ...)
    database.py     - engine init, session factory, create_tables()
    user_settings.py - UserSettingsRepo CRUD + is_blocked()
    group_repo.py   - GroupRepo CRUD + thread/user policy helpers
    download_log.py - DownloadLogRepo append-only log
    file_cache.py   - FileCacheRepo (file_id cache keyed by URL + options)
    rate_limit.py   - RateLimitRepo per-user windowed counters
    bot_settings.py - BotSettingsRepo key-value admin config
  upload/
    sender.py       - send media to Telegram (video/audio/document/photo)
    caption.py      - caption formatting
  url/
    extractor.py    - extract URLs from message text
    normalizer.py   - URL normalisation (strip tracking params, etc.)
    resolver.py     - redirect following
    domains.py      - domain extraction helpers
  utils/
    safe_telegram.py - error-tolerant Telegram helpers (delete_many, etc.)
    formatting.py    - human-readable size/duration
    errors.py        - typed download error classes
    mediainfo.py     - mediainfo CLI wrapper
  main.py           - bot entry point (post_init, job queue, polling)
```

## Shared state (context.bot_data)

| Key | Type | Description |
|-----|------|-------------|
| `settings` | `Settings` | Pydantic config loaded at startup |
| `session_factory` | `async_sessionmaker` | SQLAlchemy session factory |
| `user_repo` | `UserSettingsRepo` | user settings CRUD |
| `file_cache` | `FileCacheRepo` | Telegram file_id cache |
| `download_log` | `DownloadLogRepo` | append-only download history |
| `cookie_manager` | `CookieManager` | per-user + browser cookies |
| `group_repo` | `GroupRepo` | group/thread/policy CRUD |
| `nsfw_checker` | `NsfwChecker` | NSFW detection (loaded at startup) |
| `bot_settings_repo` | `BotSettingsRepo` | admin key-value settings |
| `am_sessions` | `dict` | ask_menu conversation sessions |
