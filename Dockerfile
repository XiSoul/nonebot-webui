ARG SOURCE_COMMIT=
ARG PYTHON_IMAGE=3.11
ARG VARIANT=
ARG APT_MIRROR=
ARG PIP_INDEX_URL=
ARG PIP_EXTRA_INDEX_URL=
ARG PIP_TRUSTED_HOST=

FROM node:20 AS frontend-build

WORKDIR /app

COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml ./
COPY frontend/package.json frontend/

RUN corepack enable && pnpm install --frozen-lockfile

COPY frontend/ frontend/

RUN pnpm -C frontend run build-only

FROM python:${PYTHON_IMAGE}${VARIANT:+-$VARIANT} AS build-stage

ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST

RUN if [ -n "$PIP_INDEX_URL$PIP_EXTRA_INDEX_URL$PIP_TRUSTED_HOST" ]; then \
      printf '[global]\n' > /etc/pip.conf; \
      if [ -n "$PIP_INDEX_URL" ]; then printf 'index-url = %s\n' "$PIP_INDEX_URL" >> /etc/pip.conf; fi; \
      if [ -n "$PIP_EXTRA_INDEX_URL" ]; then printf 'extra-index-url = %s\n' "$PIP_EXTRA_INDEX_URL" >> /etc/pip.conf; fi; \
      if [ -n "$PIP_TRUSTED_HOST" ]; then printf 'trusted-host = %s\n' "$PIP_TRUSTED_HOST" >> /etc/pip.conf; fi; \
    fi \
    && pip install poetry setuptools wheel

ENV POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

COPY pyproject.toml poetry.lock README.md ./

RUN poetry install --only main --no-root --no-interaction --no-ansi

COPY . /app
COPY --from=frontend-build /app/nb_cli_plugin_webui/dist /app/nb_cli_plugin_webui/dist

RUN pip install --no-deps .

FROM python:${PYTHON_IMAGE}${VARIANT:+-$VARIANT}

ARG APT_MIRROR

EXPOSE 18080

ENV WEBUI_BUILD=${SOURCE_COMMIT}
ENV DEBIAN_FRONTEND=noninteractive

COPY --from=build-stage /usr/local /usr/local
COPY --from=build-stage /app /app

WORKDIR /app

RUN if [ -n "$APT_MIRROR" ]; then \
      mirror="${APT_MIRROR%/}"; \
      for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/debian.list; do \
        [ -f "$f" ] || continue; \
        sed -i \
          -e "s|http://deb.debian.org/debian|${mirror}/debian|g" \
          -e "s|https://deb.debian.org/debian|${mirror}/debian|g" \
          -e "s|http://security.debian.org/debian-security|${mirror}/debian-security|g" \
          -e "s|https://security.debian.org/debian-security|${mirror}/debian-security|g" \
          -e "s|http://ftp.debian.org/debian|${mirror}/debian|g" \
          -e "s|https://ftp.debian.org/debian|${mirror}/debian|g" \
          "$f"; \
      done; \
    fi \
    && apt-get -o Acquire::http::Proxy=false -o Acquire::https::Proxy=false update \
    && apt-get -o Acquire::http::Proxy=false -o Acquire::https::Proxy=false install -y --no-install-recommends \
        libnspr4 \
        libnss3 \
        libdbus-1-3 \
        libatk1.0-0t64 \
        libatk-bridge2.0-0t64 \
        libcups2t64 \
        libxkbcommon0 \
        libatspi2.0-0t64 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libxcursor1 \
        libgbm1 \
        libgtk-3-0 \
        libasound2t64 \
    && rm -rf /var/lib/apt/lists/*

CMD nb ui run

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import json,sys,urllib.request; from pathlib import Path; path=Path('/app/config.json'); port=str((json.loads(path.read_text(encoding='utf-8')).get('port') if path.exists() else None) or '18080'); urllib.request.urlopen(f'http://127.0.0.1:{port}', timeout=5); sys.exit(0)"
