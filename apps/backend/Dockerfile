FROM python:3.12

# Unbuffered logs; compile bytecode + copy-mode cache for uv; venv on PATH.
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /uvx /bin/

# 1) Install third-party dependencies only — no project, no dev group.
#    This layer is cached until uv.lock / pyproject.toml change, so the slow
#    dependency install runs only when they actually change.
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# 2) Add project manifests + source (this layer changes on every code edit).
COPY pyproject.toml uv.lock alembic.ini ./
COPY ./app ./app

# 3) Install the project itself. Dependencies are already resolved and cached
#    above, so this is fast; --frozen skips re-resolution, --no-dev keeps the
#    runtime image lean (no pytest/mypy/ruff/black/isort/pre-commit).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

CMD ["/app/.venv/bin/fastapi", "run", "app/main.py", "--port", "80", "--host", "0.0.0.0"]
