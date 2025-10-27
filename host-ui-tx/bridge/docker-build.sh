#!/usr/bin/env zsh
# Build and run the bridge Docker image locally (macOS zsh)
set -euo pipefail
IMAGE_NAME="xcom-bridge:latest"
DIR=$(cd "$(dirname "$0")" && pwd)
cd "$DIR"

docker build -t $IMAGE_NAME .

echo "To run: docker run --rm -p 8765:8765 $IMAGE_NAME"
