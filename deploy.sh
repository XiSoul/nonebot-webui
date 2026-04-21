#!/usr/bin/env bash
#
# deploy.sh - 本地构建 Docker 镜像并部署到测试服务器
#
# 用法:
#   ./deploy.sh              # 使用 pyproject.toml 里的版本号作为 tag
#   ./deploy.sh 0.4.2        # 使用指定版本号
#
set -euo pipefail

# ---- 配置 ----
SERVER_HOST="192.168.1.35"
SERVER_USER="xisoul"
IMAGE_NAME="nonebot-webui"
CONTAINER_NAME="nonebot-webui"

# ---- Tag ----
if [ -n "${1:-}" ]; then
  TAG="$1"
else
  TAG="$(awk -F'\"' '/^version = \"/ {print $2; exit}' pyproject.toml)"
fi
VCS_REF="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

FULL_IMAGE="${IMAGE_NAME}:${TAG}"

echo "========================================"
echo " NoneBot WebUI Deploy"
echo " Image:  $FULL_IMAGE"
echo " Server: $SERVER_USER@$SERVER_HOST"
echo "========================================"

# ---- Step 1: 本地构建镜像 ----
echo ""
echo "[1/4] Building Docker image..."
docker build \
  --build-arg APP_VERSION="$TAG" \
  --build-arg VCS_REF="$VCS_REF" \
  --build-arg PYTHON_IMAGE=3.11 \
  --build-arg VARIANT=-slim \
  --build-arg APT_MIRROR="${APT_MIRROR:-${WEBUI_DEBIAN_MIRROR:-}}" \
  --build-arg PIP_INDEX_URL="${PIP_INDEX_URL:-${WEBUI_PIP_INDEX_URL:-}}" \
  --build-arg PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-${WEBUI_PIP_EXTRA_INDEX_URL:-}}" \
  --build-arg PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-${WEBUI_PIP_TRUSTED_HOST:-}}" \
  -t "$FULL_IMAGE" \
  -t "${IMAGE_NAME}:latest" \
  .

echo "Build complete: $FULL_IMAGE"

# ---- Step 2: 导出镜像 ----
echo ""
echo "[2/4] Exporting image..."
IMAGE_FILE="/tmp/${IMAGE_NAME}_${TAG}.tar"
docker save "$FULL_IMAGE" -o "$IMAGE_FILE"
echo "Saved to $IMAGE_FILE ($(du -h "$IMAGE_FILE" | cut -f1))"

# ---- Step 3: 传输到服务器 ----
echo ""
echo "[3/4] Transferring to $SERVER_HOST..."
scp "$IMAGE_FILE" "${SERVER_USER}@${SERVER_HOST}:/tmp/"
echo "Transfer complete."

# ---- Step 4: 远程部署 ----
echo ""
echo "[4/4] Deploying on remote server..."
ssh "${SERVER_USER}@${SERVER_HOST}" bash -s <<REMOTE_SCRIPT
set -e

# Load image
echo "Loading image..."
docker load -i "/tmp/${IMAGE_NAME}_${TAG}.tar"
rm -f "/tmp/${IMAGE_NAME}_${TAG}.tar"

# Stop old container
echo "Stopping old container..."
docker rm -f $CONTAINER_NAME 2>/dev/null || true

# Start new container
echo "Starting new container..."
docker run -d \
  --name $CONTAINER_NAME \
  --restart=always \
  --network host \
  -e HOST=0.0.0.0 \
  -e PORT=18080 \
  -v /home/xisoul/nonebot-webui-data/projects:/projects \
  -v /home/xisoul/nonebot-webui-external-projects:/external-projects \
  -v /home/xisoul/nonebot-webui-data/config.json:/app/config.json \
  -v /home/xisoul/nonebot-webui-data/project.json:/app/project.json \
  $FULL_IMAGE

# Health check
echo "Waiting for container to become healthy..."
for i in \$(seq 1 30); do
  STATUS=\$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $CONTAINER_NAME 2>/dev/null || echo "unknown")
  echo "  [\$i/30] status: \$STATUS"
  if [ "\$STATUS" = "healthy" ]; then
    echo "Deploy successful!"
    exit 0
  fi
  sleep 2
done

echo "Warning: container not healthy within 60s"
docker logs --tail 20 $CONTAINER_NAME
exit 1
REMOTE_SCRIPT

# Cleanup local export
rm -f "$IMAGE_FILE"

echo ""
echo "========================================"
echo " Deploy complete!"
echo " Access: http://$SERVER_HOST:18080"
echo "========================================"
