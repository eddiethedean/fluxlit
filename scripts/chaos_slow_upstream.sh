#!/usr/bin/env bash
# Local chaos check: a slow Streamlit-like upstream should produce a 502 timeout.
#
# Expected: proxied requests exceed gateway read timeout → 502 or error response;
# gateway logs show upstream timing. Align with FLUXLIT_GATEWAY_* timeout env docs.
set -euo pipefail

PORT="${PORT:-8010}"
UPSTREAM_PORT="${UPSTREAM_PORT:-8011}"
LOG_FILE="${LOG_FILE:-.fluxlit-chaos-slow-upstream.log}"

cleanup() {
  for pid in "${gateway_pid:-}" "${upstream_pid:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT

python3 - <<PY &
import http.server
import socketserver
import time

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(5)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"slow")

    def log_message(self, *args):
        pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", ${UPSTREAM_PORT}), Handler) as httpd:
    httpd.serve_forever()
PY
upstream_pid=$!

python3 - <<PY >"$LOG_FILE" 2>&1 &
import uvicorn
from fastapi import FastAPI

from fluxlit.config import FluxlitSettings
from fluxlit.gateway import build_gateway

api = FastAPI()

@api.get("/healthz")
def healthz():
    return {"status": "ok"}

settings = FluxlitSettings(gateway_upstream_read_timeout_s=0.2)
app = build_gateway(
    api,
    "http://127.0.0.1:${UPSTREAM_PORT}",
    api_prefix="/api",
    proxy_settings=settings,
)
uvicorn.run(app, host="127.0.0.1", port=${PORT}, log_level="warning")
PY
gateway_pid=$!

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

status="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/")"
if [[ "$status" == "502" ]]; then
  echo "PASS: slow upstream returned 502"
else
  echo "FAIL: expected 502 for slow upstream, got ${status}" >&2
  exit 1
fi
