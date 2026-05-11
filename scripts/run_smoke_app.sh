#!/usr/bin/env bash
# Run the canonical FluxLit smoke app locally.
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

export FLUXLIT_NO_PIDFILE=1
exec fluxlit run examples.smoke_app.app:app --host "$HOST" --port "$PORT" --no-pidfile
