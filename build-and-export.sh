#!/bin/bash

# 在测试环境构建正式版镜像的脚本
set -e

IMAGE_NAME="nonebot-webui"
IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"
OUTPUT_DIR="/tmp/docker-images"
OUTPUT_FILE="${OUTPUT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar"

echo "=== 开始构建 NoneBot WebUI 镜像 ==="
echo "镜像名称: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "输出路径: ${OUTPUT_FILE}"
echo ""

# 创建输出目录
mkdir -p "${OUTPUT_DIR}"

# 构建镜像
echo "[1/3] 构建 Docker 镜像..."
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} \
  --build-arg SOURCE_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown") \
  --build-arg PYTHON_IMAGE=3.11 \
  --build-arg VARIANT=-slim \
  .

echo ""
echo "[2/3] 导出镜像到 tar 文件..."
docker save -o "${OUTPUT_FILE}" ${IMAGE_NAME}:${IMAGE_TAG}

echo ""
echo "[3/3] 压缩镜像文件..."
gzip "${OUTPUT_FILE}"

echo ""
echo "=== 构建完成 ==="
echo "镜像已保存到: ${OUTPUT_FILE}.gz"
echo "文件大小: $(du -h ${OUTPUT_FILE}.gz | cut -f1)"
echo ""
echo "你可以使用以下命令加载镜像:"
echo "  gunzip ${OUTPUT_FILE}.gz"
echo "  docker load -i ${OUTPUT_FILE}"
echo ""
echo "或者直接运行:"
echo "  docker run -d --name nonebot-webui --network host ${IMAGE_NAME}:${IMAGE_TAG}"
