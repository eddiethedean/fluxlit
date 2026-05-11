#!/usr/bin/env bash
# Local chaos check: open and drop a Streamlit WebSocket connection.
set -euo pipefail

PORT="${PORT:-8000}"
LOG_FILE="${LOG_FILE:-.fluxlit-chaos-websocket.log}"

cleanup() {
  if [[ -n "${gateway_pid:-}" ]] && kill -0 "$gateway_pid" 2>/dev/null; then
    kill "$gateway_pid" 2>/dev/null || true
    wait "$gateway_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if ! python3 -c "import websockets" 2>/dev/null; then
  echo "FAIL: need Python package websockets (pip install websockets)" >&2
  exit 1
fi

export FLUXLIT_NO_PIDFILE=1
fluxlit run examples.smoke_app.app:app --port "$PORT" --no-pidfile >"$LOG_FILE" 2>&1 &
gateway_pid=$!

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

python3 - <<PY
import asyncio
import websockets

async def main() -> None:
    async with websockets.connect(
        "ws://127.0.0.1:${PORT}/_stcore/stream",
        subprotocols=["streamlit"],
        open_timeout=10,
    ):
        return

asyncio.run(main())
PY

curl -fsS "http://127.0.0.1:${PORT}/api/healthz" >/dev/null
echo "PASS: dropped WebSocket did not break gateway health"
