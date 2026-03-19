# Shared image for both yoink-bot and yoink-api.
# The two services are separate entrypoints of the same Python package:
#   yoink-bot  -> uv run yoink-bot  (default CMD)
#   yoink-api  -> uv run yoink-api  (overridden via compose command:)
FROM python:3.12-slim

ARG TZ=Europe/Moscow
ENV TZ="$TZ" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    mediainfo \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN useradd -u 1000 -m appuser

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/yoink/ src/yoink/
COPY src/db/ src/db/
COPY scripts/entrypoint.sh entrypoint.sh
RUN uv sync --frozen --no-dev && chmod +x entrypoint.sh && chown -R appuser:appuser /app

USER appuser

VOLUME ["/app/data"]

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uv", "run", "yoink-bot"]
