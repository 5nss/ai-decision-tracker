# syntax=docker/dockerfile:1

# ── 1. build the React app ───────────────────────────────────────────────────────
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── 2. API + static UI in one small image ───────────────────────────────────────
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Editable install keeps the package at /app/backend, so the default paths for the database,
# the eval report and the built UI resolve inside the image without extra configuration.
COPY backend/ backend/
RUN pip install -e backend
COPY --from=web /web/dist frontend/dist

RUN useradd --create-home --uid 1000 hindsight \
    && mkdir -p backend/data \
    && chown -R hindsight backend/data
USER hindsight

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
CMD ["uvicorn", "hindsight.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
