#!/bin/sh
set -e

# Only run migrations when starting the API service, not the bot.
# Both use the same image; the bot starts after the API so migrations
# are already applied by then.
SHOULD_MIGRATE=0
for arg in "$@"; do
    case "$arg" in
        yoink-api) SHOULD_MIGRATE=1 ;;
    esac
done

if [ "$SHOULD_MIGRATE" = "1" ]; then
    echo "[entrypoint] Checking Alembic state..."

    STAMP_NEEDED=$(uv run python - <<'EOF'
import os, sys
try:
    import psycopg2
    url = os.environ['DATABASE_URL'] \
        .replace('postgresql+asyncpg://', 'postgresql://') \
        .replace('postgresql+psycopg2://', 'postgresql://')
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version'")
    exists = cur.fetchone() is not None
    conn.close()
    print('no' if exists else 'yes')
except Exception as e:
    print('error:' + str(e), file=sys.stderr)
    print('skip')
EOF
)

    if [ "$STAMP_NEEDED" = "yes" ]; then
        echo "[entrypoint] First run — stamping alembic at head (schema already exists)..."
        uv run alembic -c src/db/alembic.ini stamp head
    elif [ "$STAMP_NEEDED" = "no" ]; then
        echo "[entrypoint] Running Alembic migrations..."
        uv run alembic -c src/db/alembic.ini upgrade head
    else
        echo "[entrypoint] Could not check alembic state, skipping migrations"
    fi
fi

echo "[entrypoint] Starting: $*"
exec "$@"
