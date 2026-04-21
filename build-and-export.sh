#!/usr/bin/env bash

set -euo pipefail

IMAGE_NAME="nonebot-webui"
TAG="${1:-$(git rev-parse --short HEAD 2>/dev/null || echo unknown)}"
OUTPUT_DIR="${OUTPUT_DIR:-./dist-images}"
ARCHIVE_NAME="${IMAGE_NAME}-${TAG}.tar"
ARCHIVE_PATH="${OUTPUT_DIR}/${ARCHIVE_NAME}"

mkdir -p "${OUTPUT_DIR}"

echo "=== 开始构建 NoneBot WebUI 正式版镜像 ==="
echo "镜像名称: ${IMAGE_NAME}:${TAG}"
echo "输出路径: ${ARCHIVE_PATH}"
echo

echo "[1/3] 构建 Docker 镜像..."
docker build \
  -t "${IMAGE_NAME}:${TAG}" \
  -t "${IMAGE_NAME}:latest" \
  --build-arg SOURCE_COMMIT="${TAG}" \
  --build-arg PYTHON_IMAGE=3.11 \
  --build-arg VARIANT=-slim \
  --build-arg APT_MIRROR="${APT_MIRROR:-${WEBUI_DEBIAN_MIRROR:-}}" \
  --build-arg PIP_INDEX_URL="${PIP_INDEX_URL:-${WEBUI_PIP_INDEX_URL:-}}" \
  --build-arg PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-${WEBUI_PIP_EXTRA_INDEX_URL:-}}" \
  --build-arg PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-${WEBUI_PIP_TRUSTED_HOST:-}}" \
  .

echo
echo "[2/3] 导出镜像到 tar 文件..."
docker save -o "${ARCHIVE_PATH}" "${IMAGE_NAME}:${TAG}"

echo
echo "[3/3] 完成"
echo "镜像已保存到: ${ARCHIVE_PATH}"
echo "文件大小: $(du -h "${ARCHIVE_PATH}" | cut -f1)"
echo
echo "加载镜像: docker load -i ${ARCHIVE_PATH}"
echo "运行镜像: docker run -d --name nonebot-webui --network host ${IMAGE_NAME}:${TAG}"
