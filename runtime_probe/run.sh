#!/usr/bin/env sh
set -e

IMAGE=devkitpro/devkita64
PROJECT_DIR=$(cd "$(dirname "$0")" && pwd)

docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "$PROJECT_DIR":/project -w /project "$IMAGE" make package

echo "Built $PROJECT_DIR/nx_pctl_runtime_probe.nsp"
echo "Install bundle: $PROJECT_DIR/nx_pctl_runtime_probe.zip"
