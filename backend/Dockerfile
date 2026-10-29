# syntax=docker/dockerfile:1

# ---- build: resolve the locked environment with uv -------------------------------------
FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependencies first, in their own layer: source edits then rebuild in seconds instead of
# re-downloading torch. On Linux the lockfile resolves torch from the CPU-only index.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY galeria ./galeria
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---- runtime: just Python and the virtualenv -------------------------------------------
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 galeria \
    && mkdir -p /data /models \
    && chown galeria:galeria /data /models

COPY --from=build --chown=galeria:galeria /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    GALERIA_DATA_DIR=/data \
    GALERIA_DEVICE=cpu \
    GALERIA_ALLOWED_ROOTS='["/media"]' \
    HF_HOME=/models

# /data: index, metadata, thumbnails. /models: Hugging Face cache, so the ~600 MB of weights
# download once instead of on every container start.
VOLUME ["/data", "/models"]
USER galeria
EXPOSE 8000

# The first start downloads the models, hence the long start period.
HEALTHCHECK --interval=15s --timeout=5s --start-period=180s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

CMD ["galeria", "serve", "--host", "0.0.0.0", "--port", "8000"]
