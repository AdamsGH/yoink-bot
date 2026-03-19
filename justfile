set dotenv-load := true
set shell := ["bash", "-uc"]

_default:
    @just --list

# Build & run

# Rebuild and restart: bot | api | frontend | all
build service="all":
    #!/usr/bin/env bash
    set -e
    CYAN=$'\033[36m' GREEN=$'\033[32m' DIM=$'\033[2m' BOLD=$'\033[1m' NC=$'\033[0m'
    case "{{service}}" in
        bot)            SVCS="yoink-bot" ;;
        api)            SVCS="yoink-api" ;;
        front|frontend) SVCS="yoink-frontend" ;;
        all)            SVCS="yoink-bot yoink-api yoink-frontend" ;;
        *)
            echo -e "\n  Usage: just build [bot|api|frontend|all]\n"
            exit 1 ;;
    esac
    echo -e "  ${BOLD}Building:${NC} ${CYAN}${SVCS}${NC}"
    docker compose build $SVCS
    docker compose up -d --force-recreate $SVCS
    docker image prune -f --filter "label!=keep" > /dev/null
    echo -e "  ${GREEN}✓${NC} Done."

# Start all services
up:
    docker compose up -d

# Stop all services
down:
    docker compose down

# Container status
status:
    docker compose ps

# Logs

# Follow logs: bot | api | frontend | all
logs service="all":
    #!/usr/bin/env bash
    case "{{service}}" in
        bot)            docker compose logs -f yoink-bot ;;
        api)            docker compose logs -f yoink-api ;;
        front|frontend) docker compose logs -f yoink-frontend ;;
        all)            docker compose logs -f yoink-bot yoink-api yoink-frontend ;;
        *)
            echo "Usage: just logs [bot|api|frontend|all]"
            exit 1 ;;
    esac

# Last 50 bot log lines (noise filtered)
tail:
    @docker logs yoink-bot 2>&1 | grep -v "apscheduler\|\[download\]" | tail -50

# Shell

# Shell in container: bot | api
shell service="bot":
    #!/usr/bin/env bash
    case "{{service}}" in
        bot) docker exec -it yoink-bot /bin/sh ;;
        api) docker exec -it yoink-api /bin/sh ;;
        *)
            echo "Usage: just shell [bot|api]"
            exit 1 ;;
    esac

# Database — just db <action>

# Database: connect | log | cache | cookies | schema | stats | evict | query "SQL"
db action *args:
    #!/usr/bin/env bash
    CYAN=$'\033[36m' GREEN=$'\033[32m' DIM=$'\033[2m' BOLD=$'\033[1m' NC=$'\033[0m'
    U="${POSTGRES_USER:-yoink}"
    D="${POSTGRES_DB:-yoink}"
    PG="docker exec yoink-postgres psql -U $U -d $D"
    case "{{action}}" in
        connect)
            docker exec -it yoink-postgres psql -U "$U" -d "$D"
            ;;
        log)
            $PG -c "SELECT created_at, user_id, domain, title, quality, file_size, status
                    FROM download_log ORDER BY created_at DESC LIMIT 20;"
            ;;
        cache)
            $PG -c "SELECT cache_key, file_type, title, file_size, expires_at
                    FROM file_cache ORDER BY created_at DESC LIMIT 20;"
            ;;
        cookies)
            $PG -c "SELECT user_id, domain, is_valid, updated_at
                    FROM cookies ORDER BY updated_at DESC;"
            ;;
        schema)
            echo ""
            echo -e "  ${BOLD}Tables${NC}"
            $PG -c "\dt" | tail -n +3 | head -n -2 | \
                while IFS='|' read -r _ name _ _; do
                    name=$(echo "$name" | xargs)
                    [ -n "$name" ] && printf "  ${GREEN}●${NC} ${CYAN}%s${NC}\n" "$name"
                done
            echo ""
            ;;
        stats)
            $PG -c "SELECT tablename AS \"Table\",
                        pg_size_pretty(pg_total_relation_size('public.'||tablename)) AS \"Total\",
                        pg_size_pretty(pg_table_size('public.'||tablename)) AS \"Data\",
                        (SELECT reltuples::bigint FROM pg_class
                         WHERE oid = ('public.'||tablename)::regclass) AS \"Rows\"
                    FROM pg_tables WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size('public.'||tablename) DESC;"
            ;;
        evict)
            $PG -c "DELETE FROM file_cache WHERE expires_at <= now();"
            ;;
        query)
            SQL="{{args}}"
            if [ -z "$SQL" ]; then
                echo -e "\n  Usage: just db query \"SELECT ...\"\n"
                exit 1
            fi
            $PG -c "$SQL"
            ;;
        *)
            echo ""
            echo -e "  ${BOLD}just db${NC} <action>"
            echo -e "  ${CYAN}connect${NC}        Open psql prompt"
            echo -e "  ${CYAN}log${NC}            Recent download log"
            echo -e "  ${CYAN}cache${NC}          File cache contents"
            echo -e "  ${CYAN}cookies${NC}        Stored cookies"
            echo -e "  ${CYAN}schema${NC}         List tables"
            echo -e "  ${CYAN}stats${NC}          Table sizes and row counts"
            echo -e "  ${CYAN}evict${NC}          Delete expired cache entries"
            echo -e "  ${CYAN}query${NC} \"SQL\"    Execute SQL"
            echo ""
            ;;
    esac

# Backups — just backup <action>

# Backup: create | restore <file> | list
backup action *args:
    #!/usr/bin/env bash
    set -e
    CYAN=$'\033[36m' GREEN=$'\033[32m' YELLOW=$'\033[33m' RED=$'\033[31m'
    DIM=$'\033[2m' BOLD=$'\033[1m' NC=$'\033[0m'
    U="${POSTGRES_USER:-yoink}"
    D="${POSTGRES_DB:-yoink}"
    DIR="backups"
    case "{{action}}" in
        create)
            TS=$(date +%Y%m%d_%H%M%S)
            OUT="${DIR}/yoink_${TS}.dump"
            mkdir -p "$DIR"
            echo ""
            echo -e "  ${BOLD}Creating backup${NC}"
            echo -e "  ${DIM}Output:${NC} ${CYAN}${OUT}${NC}"
            echo -e "  ${YELLOW}○${NC} Dumping..."
            docker exec yoink-postgres pg_dump -U "$U" --format=custom "$D" > "$OUT"
            SIZE=$(ls -lh "$OUT" | awk '{print $5}')
            echo -e "  ${GREEN}✓${NC} ${CYAN}${OUT}${NC} ${DIM}(${SIZE})${NC}"
            REMOVED=0
            while IFS= read -r old; do
                rm -f "$old" && ((REMOVED++)) || true
            done < <(ls -t "${DIR}"/yoink_*.dump 2>/dev/null | tail -n +11)
            [ $REMOVED -gt 0 ] && echo -e "  ${DIM}Removed ${REMOVED} old backup(s)${NC}"
            echo ""
            ;;
        restore)
            FILE="{{args}}"
            if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
                [ -z "$FILE" ] && echo -e "\n  Usage: just backup restore <file>\n" \
                               || echo -e "\n  ${RED}File not found:${NC} $FILE\n"
                exit 1
            fi
            SIZE=$(ls -lh "$FILE" | awk '{print $5}')
            echo ""
            echo -e "  ${BOLD}${RED}Database restore${NC}"
            echo -e "  ${DIM}File:${NC}   ${CYAN}$(basename "$FILE")${NC} ${DIM}(${SIZE})${NC}"
            echo -e "  ${DIM}Target:${NC} ${RED}${D} — this will replace all data${NC}"
            echo ""
            read -rp "  Type 'yes' to confirm: "
            if [ "$REPLY" != "yes" ]; then
                echo -e "\n  ${YELLOW}Cancelled.${NC}\n"; exit 1
            fi
            echo -e "  ${YELLOW}○${NC} Restoring..."
            cat "$FILE" | docker exec -i yoink-postgres pg_restore \
                -U "$U" -d "$D" --clean --if-exists 2>&1 | grep -v "already exists" || true
            echo -e "  ${GREEN}✓${NC} Restore complete."
            echo ""
            ;;
        list)
            echo ""
            echo -e "  ${BOLD}Available backups${NC}"
            if [ ! -d "$DIR" ] || [ -z "$(ls "${DIR}"/yoink_*.dump 2>/dev/null)" ]; then
                echo -e "  ${DIM}No backups found. Run: ${CYAN}just backup create${NC}"
                echo ""; exit 0
            fi
            ls -lht "${DIR}"/yoink_*.dump 2>/dev/null | \
            while read -r _ _ _ _ size _ _ _ file; do
                fname=$(basename "$file")
                [[ "$fname" =~ ([0-9]{8})_([0-9]{6}) ]] && \
                    ts="${BASH_REMATCH[1]:0:4}-${BASH_REMATCH[1]:4:2}-${BASH_REMATCH[1]:6:2} ${BASH_REMATCH[2]:0:2}:${BASH_REMATCH[2]:2:2}"
                printf "  ${GREEN}●${NC} ${CYAN}%-42s${NC} ${DIM}%6s  %s${NC}\n" "$fname" "$size" "$ts"
            done
            echo ""
            ;;
        *)
            echo ""
            echo -e "  ${BOLD}just backup${NC} <action>"
            echo -e "  ${CYAN}create${NC}           Create timestamped pg_dump (keeps last 10)"
            echo -e "  ${CYAN}restore${NC} <file>   Restore from dump file"
            echo -e "  ${CYAN}list${NC}             List available backups"
            echo ""
            ;;
    esac

# Migrations — just migrate <action>

# Migrate: up | down | create "msg" | current | history
migrate action *args:
    #!/usr/bin/env bash
    set -e
    CYAN=$'\033[36m' GREEN=$'\033[32m' YELLOW=$'\033[33m'
    DIM=$'\033[2m' BOLD=$'\033[1m' NC=$'\033[0m'
    # up/down/current/history run inside the already-running yoink-api container
    # (no local psycopg2 needed, migrations dir is mounted).
    # create runs a throw-away container with the *current host source tree* mounted
    # so autogenerate always sees the latest models, not the baked image.
    ALB_EXEC="docker compose exec yoink-api uv run alembic -c src/db/alembic.ini"
    ALB_RUN="docker run --rm \
        --network yoink-bot_yoink \
        -e DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-yoink}:${POSTGRES_PASSWORD}@yoink-postgres:5432/${POSTGRES_DB:-yoink} \
        -v $(pwd)/src:/app/src \
        -w /app \
        yoink/api:latest \
        uv run alembic -c src/db/alembic.ini"
    case "{{action}}" in
        up)
            echo -e "  ${YELLOW}○${NC} Applying migrations..."
            $ALB_EXEC upgrade head
            echo -e "  ${GREEN}✓${NC} Done."
            ;;
        down)
            echo -e "  ${YELLOW}○${NC} Rolling back one migration..."
            $ALB_EXEC downgrade -1
            echo -e "  ${GREEN}✓${NC} Done."
            ;;
        create)
            MSG="{{args}}"
            if [ -z "$MSG" ]; then
                echo -e "\n  Usage: just migrate create \"message\"\n"; exit 1
            fi
            echo ""
            echo -e "  ${BOLD}Creating migration:${NC} ${CYAN}${MSG}${NC}"
            echo -e "  ${DIM}Using host source tree — autogenerate sees current models.${NC}"
            $ALB_RUN revision --autogenerate -m "$MSG"
            echo ""
            echo -e "  ${YELLOW}!${NC} Review the generated file before applying."
            echo -e "  ${YELLOW}!${NC} NOT NULL columns on existing tables need server_default in upgrade()."
            echo -e "  ${YELLOW}!${NC} Run ${CYAN}just migrate up${NC} when ready."
            echo ""
            ;;
        current)
            $ALB_EXEC current
            ;;
        history)
            $ALB_EXEC history --verbose
            ;;
        *)
            echo ""
            echo -e "  ${BOLD}just migrate${NC} <action>"
            echo -e "  ${CYAN}up${NC}               Apply all pending migrations"
            echo -e "  ${CYAN}down${NC}             Roll back one migration"
            echo -e "  ${CYAN}create${NC} \"msg\"    Autogenerate + apply"
            echo -e "  ${CYAN}current${NC}          Show current revision"
            echo -e "  ${CYAN}history${NC}          Show full history"
            echo ""
            ;;
    esac

# Cookies — just cookies <action>

# Cookies: browser | stop | list | grab <site>
cookies action *args:
    #!/usr/bin/env bash
    case "{{action}}" in
        browser)
            docker compose --profile cookies up -d kasm-chromium
            echo ""
            echo "  Open the kasm-chromium URL configured in your environment"
            echo "  Export cookies to ~/cookies/<domain>.txt inside the browser"
            echo ""
            ;;
        stop)
            docker compose --profile cookies stop kasm-chromium
            docker compose --profile cookies rm -f kasm-chromium
            ;;
        list)
            ls -lh data/cookies/*.txt 2>/dev/null || echo "No cookie files in data/cookies/"
            ;;
        grab)
            SITE="{{args}}"
            if [ -z "$SITE" ]; then
                echo "Usage: just cookies grab <site>"; exit 1
            fi
            uv run python scripts/grab_cookies.py --site "$SITE" --upload \
                --bot-url "${TELEGRAM_BASE_URL:-http://localhost:8081/bot}" \
                --token "${BOT_TOKEN}" \
                --owner-id "${OWNER_ID}"
            ;;
        *)
            echo ""
            echo "  just cookies <action>"
            echo "  browser          Start kasm-chromium for cookie capture"
            echo "  stop             Stop kasm-chromium"
            echo "  list             List captured cookie files"
            echo "  grab <site>      Upload cookie file to bot"
            echo ""
            ;;
    esac

# Dev

# Run tests
test:
    PYTHONDONTWRITEBYTECODE=1 uv run pytest src/tests/ -v

# Pyright type check
typecheck:
    PYTHONDONTWRITEBYTECODE=1 uv run pyright src/ || true

# Publish a sanitized snapshot to the public mirror.
# Usage: just publish "feat: add something"
publish message="":
    #!/usr/bin/env bash
    set -e
    if [[ -z "{{message}}" ]]; then
        echo ""
        echo "  Usage: just publish \"commit message\""
        echo ""
        exit 1
    fi
    gh workflow run sync-public.yml \
        --repo AdamsGH/yoink-bot-private \
        --field message="{{message}}"
    echo "Sync triggered. Follow progress at:"
    echo "  https://github.com/AdamsGH/yoink-bot-private/actions"

# Remove __pycache__, egg-info and other build artifacts from host
clean-pyc:
    find . -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.egg-info" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null || true
    @echo "done"
