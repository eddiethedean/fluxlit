#!/usr/bin/env bash
# Subprocess smoke: start ``fluxlit run`` on the canonical smoke app and probe
# ``/api/healthz`` then ``/api/readyz`` (readiness waits for Streamlit).
#
# Used by CI (Ubuntu). Requires bash, curl, and a FluxLit dev install on PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}/examples/smoke_app"

PORT="${FLUXLIT_SMOKE_PORT:-18765}"
HOST="${FLUXLIT_SMOKE_HOST:-127.0.0.1}"
BASE="http://${HOST}:${PORT}"

fluxlit run app:app --host "${HOST}" --port "${PORT}" &
PID=$!

cleanup() {
  if kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "${PID}" 2>/dev/null || break
      sleep 0.2
    done
    kill -9 "${PID}" 2>/dev/null || true
  fi
  wait "${PID}" 2>/dev/null || true
}
trap cleanup EXIT

echo "smoke_fluxlit_run: waiting for healthz at ${BASE}/api/healthz"
for _ in $(seq 1 120); do
  if curl -sf "${BASE}/api/healthz" >/dev/null; then
    break
  fi
  sleep 0.5
done
curl -sf "${BASE}/api/healthz" >/dev/null

echo "smoke_fluxlit_run: waiting for readyz=200 at ${BASE}/api/readyz"
code="000"
for _ in $(seq 1 180); do
  code="$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/api/readyz" || echo 000)"
  if [[ "${code}" == "200" ]]; then
    break
  fi
  sleep 0.5
done
if [[ "${code}" != "200" ]]; then
  echo "smoke_fluxlit_run: FAIL readyz never reached 200 (last=${code})" >&2
  exit 1
fi

echo "smoke_fluxlit_run: OK (healthz + readyz)"
