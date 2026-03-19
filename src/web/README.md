# yoink frontend

Telegram Mini App built with React 19, Vite 6, Tailwind 4, shadcn/ui and Refine 4.
Served by nginx in production; nginx also proxies `/api/*` to `yoink-api`.

## Stack

- **React 19** + **TypeScript** (strict mode)
- **Vite 6** - build tool
- **Tailwind CSS 4** - utility styling
- **shadcn/ui** - component primitives (do not modify files under `src/components/ui/`)
- **Refine 4** - data fetching and auth wiring
- **Catppuccin** - theme system (latte / frappe / macchiato / mocha)

## Structure

```
src/
  components/
    ui/          - shadcn primitives (untouchable)
    UserPanel    - identity sheet shown in sidebar and mobile nav
  layout/
    AppLayout    - sidebar + mobile bottom nav with admin drawer
    TelegramProvider - Telegram WebApp SDK wrapper, theme/flavor management
  lib/
    api-client   - axios instance pre-configured with JWT header
    auth-provider - Refine auth adapter (reads role from JWT)
    data-provider - Refine data adapter
    utils        - cn(), formatDate(), decodeJwt()
  pages/
    settings/    - user preferences (quality, proxy, subtitles, theme)
    history/     - download log with retry and open-in-Telegram
    admin/
      users/     - role management, bans, search
      groups/    - enable/disable groups, NSFW policy, thread policies
      cookies/   - upload and delete site cookies
      nsfw/      - domain blocklist, keyword lists, NSFW check debugger
      stats/     - download volume charts, top domains
      bot-settings/ - access mode, browser cookies min role
  types/
    api.ts       - TypeScript interfaces matching the FastAPI response schemas
```

## Development

All package operations must run inside Docker - never run `npm install` on the host.

```bash
# Build and start the production container
just build frontend

# Rebuild after dependency changes
docker compose exec yoink-frontend sh  # not applicable for prod nginx image
# Instead: rebuild the image
just build frontend
```

## Auth

The Mini App receives Telegram `initData` on launch. `TelegramProvider` extracts the
`telegram_id` and posts it to `POST /api/v1/auth/token`, storing the returned JWT in
`localStorage`. Refine reads the role from the JWT payload for permission checks.

Pages and nav items are filtered by role at render time. The API enforces the same
roles server-side independently.
