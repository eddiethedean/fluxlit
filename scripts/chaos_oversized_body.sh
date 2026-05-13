#!/usr/bin/env bash
# Local chaos check: verify oversized proxied bodies fail with 413.
#
# Expected: HTTP 413 when body exceeds FLUXLIT_GATEWAY_MAX_PROXY_REQUEST_BODY_BYTES
# (or configured limit). See docs/cookbook.md and docs/configuration.md.
set -euo pipefail

PORT="${PORT:-8000}"
LIMIT_BYTES="${LIMIT_BYTES:-32}"
LOG_FILE="${LOG_FILE:-.fluxlit-chaos-oversized.log}"

cleanup() {
  if [[ -n "${gateway_pid:-}" ]] && kill -0 "$gateway_pid" 2>/dev/null; then
    kill "$gateway_pid" 2>/dev/null || true
    wait "$gateway_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

export FLUXLIT_NO_PIDFILE=1
export FLUXLIT_GATEWAY_MAX_PROXY_REQUEST_BODY_BYTES="$LIMIT_BYTES"
fluxlit run examples.smoke_app.app:app --port "$PORT" --no-pidfile >"$LOG_FILE" 2>&1 &
gateway_pid=$!

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

status="$(
  python3 - <<PY
import urllib.error
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:${PORT}/streamlit-upload",
    data=b"x" * (${LIMIT_BYTES} + 16),
    method="POST",
)
try:
    urllib.request.urlopen(req, timeout=10)
    print("200")
except urllib.error.HTTPError as exc:
    print(exc.code)
PY
)"

if [[ "$status" == "413" ]]; then
  echo "PASS: oversized proxied body returned 413"
else
  echo "FAIL: expected 413, got ${status}" >&2
  exit 1
fi
