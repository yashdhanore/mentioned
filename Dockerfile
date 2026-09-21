FROM python:3.12.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency layer first, from the lockfile alone, so code-only changes don't
# reinstall every dependency. --no-install-project skips building/installing
# this package itself; the API and worker both run straight from the ./src
# copy below via file path / `python -m`, so there is exactly one copy of the
# code in the image, not one in /app/src and a second in site-packages.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY src ./src

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

CMD ["sh", "scripts/render-start-api.sh"]
