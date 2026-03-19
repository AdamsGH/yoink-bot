# yoink-bot

Telegram media downloader bot. Send a link  - get the file.

Powered by **yt-dlp** + **gallery-dl**, with a FastAPI backend and a Telegram Mini App frontend.

## Architecture

```
Telegram  ──►  yoink-bot (PTB 22)
                    │
              yoink-api (FastAPI)  ──►  PostgreSQL
                    │
              yoink-frontend (nginx + React Mini App)
                    │
              tg-bot-api  (local Bot API, 2 GB uploads)
              bgutil-provider  (YouTube PO token)
```

| Service | Image | Role |
|---------|-------|------|
| `yoink-bot` | `yoink/bot` | PTB bot process, all commands and downloads |
| `yoink-api` | `yoink/api` | FastAPI, JWT auth, admin REST endpoints |
| `yoink-frontend` | `yoink/frontend` | nginx serving the React Mini App, proxies `/api/*` to yoink-api |
| `yoink-postgres` | `postgres:17-alpine` | primary database |
| `tg-bot-api` | `aiogram/telegram-bot-api` | local Bot API server enabling 2 GB uploads |
| `bgutil-provider` | `brainicism/bgutil-ytdlp-pot-provider` | YouTube PO token for age-restricted content |
| `kasm-chromium` | `kasmweb/chromium` | headless Chromium for browser cookie extraction |

## Requirements

- Docker + Docker Compose
- [`just`](https://github.com/casey/just) command runner
- Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

```bash
cp .env.example .env
# edit .env: BOT_TOKEN, OWNER_ID, POSTGRES_PASSWORD, JWT_SECRET_KEY,
#            YOINK_DOMAIN, TELEGRAM_BASE_URL, YOUTUBE_POT_URL
just up
just migrate up
```

Migrations run automatically on `yoink-api` startup via `scripts/entrypoint.sh`.
`just migrate up` is only needed after pulling new migration files manually.

## just commands

```
just build [bot|api|frontend|all]   rebuild image(s) and restart; prunes dangling layers
just up                             start all services
just down                           stop all services
just status                         container status
just logs  [bot|api|frontend|all]   follow logs
just tail                           last 50 bot log lines (noise filtered)
just shell [bot|api]                sh inside container

just migrate up                     apply pending migrations
just migrate down                   roll back one migration
just migrate create "message"       autogenerate migration from current models + prompt to review
just migrate current                show active revision
just migrate history                full migration history

just test                           run pytest (57 tests, no live DB needed)
just typecheck                      pyright type check

just db                             psql prompt
just db-log                         recent download_log rows
just db-cache                       file cache contents
just db-cookies                     stored cookies

just cookies browser                launch kasm-chromium for cookie capture
just cookies stop                   stop kasm-chromium
just cookies list                   list captured cookie files
just cookies grab <site>            upload a cookie file into the bot
```

## Bot commands

### Download (everyone)

| Command | Description |
|---------|-------------|
| _(any URL in private chat)_ | auto-detect and download |
| `/video <url>` | download video |
| `/audio <url>` | download audio only |
| `/image <url>` | download images via gallery-dl |
| `/cut <url> [start] [end]` | cut a clip (interactive or inline times) |
| `/playlist <url>` | download a playlist range |
| `/link <url>` | get direct download link |
| `/search <query>` | YouTube search |

### Settings (everyone)

| Command | Description |
|---------|-------------|
| `/settings` | overview of current settings |
| `/format` | video quality / codec / container |
| `/lang` | bot language |
| `/subs` | subtitle language and options |
| `/split` | split large files threshold |
| `/keyboard` | reply keyboard layout |
| `/nsfw` | NSFW blur toggle |
| `/proxy` | personal proxy URL |
| `/cookie` | upload site cookies (Netscape format) |
| `/mediainfo` | mediainfo report toggle |
| `/args` | custom yt-dlp arguments |
| `/clean` | reset settings to defaults |
| `/list <url>` | list available formats |
| `/tags <url>` | show metadata tags |

### Moderator+

| Command | Description |
|---------|-------------|
| `/get_log <user_id>` | user's download history |
| `/usage <user_id>` | usage statistics |

### Admin+

| Command | Description |
|---------|-------------|
| `/block <user_id>` | ban user permanently |
| `/unblock <user_id>` | unban user |
| `/ban_time <user_id> <hours>` | temporary ban |
| `/broadcast <text>` | message all users |
| `/uncache <url>` | clear a URL from file cache |
| `/reload_cache` | reload file cache from DB |
| `/group enable\|disable` | activate or silence bot in current group |
| `/group info\|allow_pm\|nsfw\|role` | group-level settings |
| `/thread allow\|deny\|list\|reset` | per-thread access control |

### Owner only

| Command | Description |
|---------|-------------|
| `/runtime` | bot runtime info |

## Access control

**Roles** (highest to lowest): `owner` → `admin` → `moderator` → `user` → `restricted` → `banned`

**Private chats:** controlled by `bot_access_mode` in Admin › Bot Settings:
- `open` (default)  - anyone can use the bot; new users get `user` role automatically
- `approved_only`  - new users get `restricted` (no access) until manually promoted

**Groups:** bot silently ignores all requests in a group until an admin runs `/group enable` or toggles it in Admin › Groups.

## Frontend (Mini App)

Opened via the bot menu button. Pages visible depend on role.

| Page | Min role | Description |
|------|----------|-------------|
| Settings | user | quality, codec, language, proxy, subtitles, theme |
| History | user | download log, retry button, open-in-Telegram link |
| Admin › Users | admin | role management, bans, search/filter |
| Admin › Groups | admin | enable/disable groups, NSFW policy, thread policies |
| Admin › Cookies | moderator | upload and delete site cookies |
| Admin › NSFW | admin | domain blocklist, URL/metadata keyword lists, test checker |
| Admin › Stats | admin | download volume, top domains, error rate |
| Admin › Bot Settings | admin | access mode, browser cookies min role |

## Downloads

**Engines:**
- **yt-dlp**  - video/audio from YouTube, Twitter/X, TikTok, Reddit, Twitch, and [1000+ sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- **gallery-dl**  - image galleries from Instagram, Pixiv, DeviantArt, etc. (via `/image`)
- Engine fallback: `ytdlp_then_gallery` tries yt-dlp first, falls back to gallery-dl

**Cookies:**
- Per-user cookies uploaded via `/cookie` or Admin › Cookies (Netscape format)
- Shared browser profile: Chromium cookies extracted automatically from `kasm-chromium` (`data/browser-profile`); access controlled by `browser_cookies_min_role` setting

## NSFW detection

Three independent layers, any match flags content as NSFW:
1. **Domain list**  - known adult domains (managed in Admin › NSFW)
2. **URL keywords**  - path/query string matching
3. **Metadata keywords**  - title and tags from yt-dlp/gallery-dl info dict

**Policy:**
- Private chats: NSFW content delivered with spoiler blur (respects user `nsfw_blur` setting)
- Groups: blocked unless `nsfw_allowed = true` on the group; always delivered with spoiler

## Migrations

Migration files live in `db/migrations/versions/`. The `db/` directory is bind-mounted into `yoink-api` so new files appear on the host immediately.

```bash
# Create a new migration (uses host source tree for accurate autogenerate)
just migrate create "add some column"
# Review the generated file  - add server_default for NOT NULL columns on existing tables
just migrate up
```

> `just migrate create` spawns a throw-away container with `./src` mounted so autogenerate
> always sees the current models, not the baked image. It does NOT auto-apply; review first.

## Tech stack

| Layer | Stack |
|-------|-------|
| Bot | python-telegram-bot 22.7, Python 3.12 |
| API | FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2 |
| DB | PostgreSQL 17 |
| Downloads | yt-dlp, gallery-dl, ffmpeg |
| Frontend | React 19, Vite 6, Tailwind 4, shadcn/ui, Refine 4 |
| Serving | nginx (static + `/api/*` proxy with dynamic DNS resolver) |
| Package mgmt | uv (Python), npm (frontend, container-only) |
