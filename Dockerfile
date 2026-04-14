ARG SOURCE_COMMIT=
ARG PYTHON_IMAGE=3.11
ARG VARIANT=

FROM node:20 AS frontend-build

WORKDIR /app

# Copy package files first for better caching
COPY package.json pnpm-lock.yaml* ./
COPY frontend/package.json frontend/

# Install dependencies
RUN corepack enable && pnpm install --frozen-lockfile

# Copy source code
COPY frontend/ frontend/

# Build frontend
RUN pnpm -C frontend run build-only

FROM python:${PYTHON_IMAGE}${VARIANT:+-$VARIANT} AS build-stage

RUN pip install poetry setuptools

ENV POETRY_VIRTUALENVS_CREATE=false

COPY . /app
COPY --from=frontend-build /app/nb_cli_plugin_webui/dist /app/nb_cli_plugin_webui/dist

WORKDIR /app

RUN poetry install --no-interaction --no-ansi

FROM python:${PYTHON_IMAGE}${VARIANT}

EXPOSE 18080

ENV WEBUI_BUILD=${SOURCE_COMMIT}

COPY --from=build-stage /usr/local /usr/local
COPY --from=build-stage /app /app

WORKDIR /app

CMD nb ui run

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD sh -c 'PORT=$(python -c "import json; from pathlib import Path; path = Path(\"/app/config.json\"); print(str(json.loads(path.read_text(encoding=\"utf-8\")).get(\"port\") or \"18080\") if path.exists() else \"18080\")"); httpx --verbose --follow-redirects http://127.0.0.1:${PORT}'
