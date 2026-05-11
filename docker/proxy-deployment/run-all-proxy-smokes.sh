#!/usr/bin/env bash
# Run root, strip-prefix, full-path, and HTTPS proxy smoke tests (sequential).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! python3 -c "import websockets" 2>/dev/null; then
  echo "Installing websockets for smoke_ws.py ..."
  python3 -m pip install -q websockets
fi

cleanup() {
  docker compose -f docker-compose.yml -f docker-compose.root.yml down -v 2>/dev/null || true
  docker compose -f docker-compose.yml down -v 2>/dev/null || true
  docker compose -f docker-compose.yml -f docker-compose.fullpath.yml down -v 2>/dev/null || true
  docker compose -f docker-compose.yml -f docker-compose.https.yml down -v 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Root proxy (8082) ==="
docker compose -f docker-compose.yml -f docker-compose.root.yml up -d --build
PUBLIC_PREFIX="" BASE_URL=http://127.0.0.1:8082 ./smoke-test.sh
docker compose -f docker-compose.yml -f docker-compose.root.yml down -v

echo "=== Strip-prefix proxy (8080) ==="
docker compose -f docker-compose.yml up -d --build
BASE_URL=http://127.0.0.1:8080 ./smoke-test.sh
docker compose -f docker-compose.yml down -v

echo "=== Full-path proxy (8081) ==="
docker compose -f docker-compose.yml -f docker-compose.fullpath.yml up -d --build
BASE_URL=http://127.0.0.1:8081 ./smoke-test.sh
docker compose -f docker-compose.yml -f docker-compose.fullpath.yml down -v

echo "=== HTTPS proxy (8444) ==="
./generate-test-certs.sh
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
CURL_INSECURE=1 BASE_URL=https://127.0.0.1:8444 ./smoke-test.sh
docker compose -f docker-compose.yml -f docker-compose.https.yml down -v

trap - EXIT
echo "All proxy smoke scenarios passed."
