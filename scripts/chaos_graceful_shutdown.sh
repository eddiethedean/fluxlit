#!/usr/bin/env bash
# Local chaos check: verify the gateway exits after SIGTERM.
#
# Expected: /api/healthz returns 200 while up; after SIGTERM the parent exits within
# TIMEOUT_S (default 20s). Logs in LOG_FILE — look for graceful drain / lifespan.
# Pair with docs/runbooks.md (Kubernetes graceful shutdown) and docs/deployment.md.
set -euo pipefail

PORT="${PORT:-8000}"
LOG_FILE="${LOG_FILE:-.fluxlit-chaos-shutdown.log}"
TIMEOUT_S="${TIMEOUT_S:-20}"

export FLUXLIT_NO_PIDFILE=1
fluxlit run examples.smoke_app.app:app --port "$PORT" --no-pidfile >"$LOG_FILE" 2>&1 &
gateway_pid=$!

cleanup() {
  if kill -0 "$gateway_pid" 2>/dev/null; then
    kill "$gateway_pid" 2>/dev/null || true
    wait "$gateway_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
curl -fsS "http://127.0.0.1:${PORT}/api/healthz" >/dev/null

kill "$gateway_pid"
for _ in $(seq 1 "$TIMEOUT_S"); do
  if ! kill -0 "$gateway_pid" 2>/dev/null; then
    echo "PASS: gateway exited after SIGTERM"
    trap - EXIT
    exit 0
  fi
  sleep 1
done

echo "FAIL: gateway still running after ${TIMEOUT_S}s" >&2
exit 1
