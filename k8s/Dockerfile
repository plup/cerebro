# Cerebro API image — `uv sync` into system Python (no `.venv` directory).
# See https://docs.astral.sh/uv/concepts/projects/config/#project-environment-path
# https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /uvx /bin/

# Official `python` images use this prefix; sync installs into that env instead of `.venv`.
ENV UV_PROJECT_ENVIRONMENT=/usr/local
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependency layer: invalidates when project metadata / lock change.
# README.md is required by [project] readme (Hatchling validates it during the build).
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Application layer: rebuilds when source changes, reuses dependency layer above.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

CMD ["uvicorn", "cerebro.api:app", "--host", "0.0.0.0", "--no-use-colors", "--log-level", "info"]
