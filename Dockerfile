# One image serves both halves: the API, and the built frontend it hands to
# browsers, so the deployed app is a single URL with no CORS between them.

FROM node:22-slim AS web
WORKDIR /web
RUN npm install -g pnpm@11.15.1
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist ./static

ENV KATARIBE_STATIC_DIR=/app/static \
    KATARIBE_DATA_DIR=/data \
    PATH="/app/.venv/bin:$PATH"

# Cloud Run sets PORT.
CMD ["sh", "-c", "exec uvicorn kataribe.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
