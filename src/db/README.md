# db

Alembic configuration and migration scripts.

```
db/
  alembic.ini          - Alembic config (database URL read from DATABASE_URL env var)
  migrations/
    env.py             - migration environment; imports SQLAlchemy models for autogenerate
    versions/          - migration files, applied in revision order
```

## Running migrations

```bash
just migrate up          # apply all pending migrations
just migrate down        # roll back one migration
just migrate current     # show active revision
just migrate history     # full migration history
```

## Creating a new migration

```bash
just migrate create "describe what changed"
```

This runs autogenerate in a throw-away container with the current host source tree mounted,
so it always sees the latest models rather than the baked image. The generated file is
written directly to `db/migrations/versions/` via the bind mount.

**Always review the generated file before applying.** In particular:
- `NOT NULL` columns added to existing tables need a `server_default` in `upgrade()`,
  then a second `alter_column` call to drop the default after backfill.
- Alembic does not detect renamed columns or tables - write those by hand.

## Connection

Migrations run against the URL in `DATABASE_URL`. Inside the running `yoink-api` container
this resolves to the `yoink-postgres` service. The `env.py` converts `asyncpg` URLs to
`psycopg2` automatically for the synchronous Alembic runner.
