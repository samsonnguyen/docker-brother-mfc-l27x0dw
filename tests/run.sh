#!/bin/bash
# Builds the image, starts it the way production does, and runs the driver
# checks against the live cupsd inside it.
set -euo pipefail

IMAGE=${IMAGE:-brother-mfc-l27x0dw:test}
CONTAINER=brother-driver-selftest
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)

cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "==> building $IMAGE"
docker build --platform linux/amd64 -t "$IMAGE" "$REPO_ROOT"

echo "==> starting container"
cleanup
docker run -d --name "$CONTAINER" --platform linux/amd64 \
    -e MODEL=Brother-MFC-L2700DW \
    -e PRINTER_NAME=Brother-MFC-L2700DW \
    -e PRINTER_IP=127.0.0.1 \
    -v "$REPO_ROOT/tests:/tests:ro" \
    "$IMAGE" >/dev/null

echo "==> waiting for the queue to be registered"
# `lpstat -r` exits 0 even when the scheduler is down, so wait on the queue.
for _ in $(seq 60); do
    if docker exec "$CONTAINER" lpstat -p 2>/dev/null | grep -q '^printer'; then break; fi
    sleep 0.5
done

echo "==> running driver checks"
docker exec "$CONTAINER" bash /tests/test-drivers.sh
