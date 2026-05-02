ARG APP_VERSION=0.4.6
ARG VCS_REF=
ARG PYTHON_IMAGE=3.11
ARG VARIANT=
ARG APT_MIRROR=
ARG PIP_INDEX_URL=
ARG PIP_EXTRA_INDEX_URL=
ARG PIP_TRUSTED_HOST=

FROM node:22 AS frontend-build

WORKDIR /app

COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml ./
COPY frontend/package.json frontend/

RUN corepack enable && pnpm install --frozen-lockfile

COPY frontend/ frontend/

RUN pnpm -C frontend run build-only

FROM python:${PYTHON_IMAGE}${VARIANT:+-$VARIANT} AS build-stage

ARG APP_VERSION=0.4.6
ARG VCS_REF=unknown
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

ARG APP_VERSION=0.4.6
ARG VCS_REF=unknown
ARG APT_MIRROR
EXPOSE 18080

# 创建挂载目录
RUN mkdir -p /opt/nonebot-projects && chmod 777 /opt/nonebot-projects

LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.revision="${VCS_REF}"

ENV WEBUI_BUILD=1
ENV WEBUI_VERSION=${APP_VERSION}
ENV WEBUI_VCS_REF=${VCS_REF}
ENV DEBIAN_FRONTEND=noninteractive

COPY --from=build-stage /usr/local /usr/local
COPY --from=build-stage /app /app

WORKDIR /app

RUN mkdir -p /usr/local/share/nb-cli-plugin-webui \
    && printf '%s' "${APP_VERSION}" > /usr/local/share/nb-cli-plugin-webui/version \
    && printf '%s' "${VCS_REF}" > /usr/local/share/nb-cli-plugin-webui/revision

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
        libasound2t64 \
        libatk1.0-0t64 \
        libatk-bridge2.0-0t64 \
        libatomic1 \
        libcairo2 \
        libevent-2.1-7t64 \
        libatspi2.0-0t64 \
        libcups2t64 \
        libdbus-1-3 \
        libdrm2 \
        libegl1 \
        libenchant-2-2 \
        libepoxy0 \
        libevdev2 \
        libflite1 \
        libfontconfig1 \
        libfreetype6 \
        libgbm1 \
        libgdk-pixbuf-2.0-0 \
        libgles2 \
        libglib2.0-0t64 \
        libglx0 \
        libgraphene-1.0-0 \
        libgstreamer1.0-0 \
        libgstreamer-gl1.0-0 \
        libgstreamer-plugins-bad1.0-0 \
        libgstreamer-plugins-base1.0-0 \
        libgtk-3-0t64 \
        libgtk-4-1 \
        libgudev-1.0-0 \
        libharfbuzz-icu0 \
        libharfbuzz0b \
        libhyphen0 \
        libicu76 \
        libjpeg62-turbo \
        libjxl0.11 \
        liblcms2-2 \
        libmanette-0.2-0 \
        libnotify4 \
        libnspr4 \
        libnss3 \
        libopengl0 \
        libopus0 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpng16-16t64 \
        libproxy1v5 \
        libsecret-1-0 \
        libsoup-3.0-0 \
        libvpx9 \
        libavif16 \
        libwayland-client0 \
        libwayland-egl1 \
        libwayland-server0 \
        libwebp7 \
        libwebpdemux2 \
        libwebpmux3 \
        libwoff1 \
        libx11-6 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libxcursor1 \
        libxext6 \
        libxi6 \
        libxkbcommon0 \
        libxml2 \
        libxslt1.1 \
        libx264-164 \
        libxrender1 \
        libx11-xcb1 \
        libxcb-shm0 \
        libxcb1 \
        libxtst6 \
        libvulkan1 \
    && ln -sf /usr/lib/x86_64-linux-gnu/libx264.so.164 /usr/lib/x86_64-linux-gnu/libx264.so \
    && rm -rf /var/lib/apt/lists/*

CMD ["nb", "ui", "run"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import json,sys,urllib.request; from pathlib import Path; path=Path('/app/config.json'); port=str((json.loads(path.read_text(encoding='utf-8')).get('port') if path.exists() else None) or '18080'); urllib.request.urlopen(f'http://127.0.0.1:{port}', timeout=5); sys.exit(0)"
