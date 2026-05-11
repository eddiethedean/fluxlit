#!/usr/bin/env bash
# Local chaos check: kill the Streamlit sidecar and confirm the gateway exits.
set -euo pipefail

PORT="${PORT:-8000}"
LOG_FILE="${LOG_FILE:-.fluxlit-chaos.log}"

cleanup() {
  if [[ -n "${gateway_pid:-}" ]] && kill -0 "$gateway_pid" 2>/dev/null; then
    kill "$gateway_pid" 2>/dev/null || true
    wait "$gateway_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

export FLUXLIT_NO_PIDFILE=1
fluxlit run examples.smoke_app.app:app --port "$PORT" --no-pidfile >"$LOG_FILE" 2>&1 &
gateway_pid=$!

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

curl -fsS "http://127.0.0.1:${PORT}/api/healthz" >/dev/null

sidecar_pid="$(pgrep -P "$gateway_pid" -f 'streamlit run' | head -n 1 || true)"
if [[ -z "$sidecar_pid" ]]; then
  echo "FAIL: could not find Streamlit child process for gateway pid ${gateway_pid}" >&2
  exit 1
fi

kill "$sidecar_pid"

for _ in $(seq 1 60); do
  if ! kill -0 "$gateway_pid" 2>/dev/null; then
    echo "PASS: gateway exited after Streamlit sidecar was killed"
    exit 0
  fi
  sleep 0.5
done

echo "FAIL: gateway did not exit after killing Streamlit sidecar" >&2
exit 1
