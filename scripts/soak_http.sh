#!/usr/bin/env bash
# Lightweight soak: repeated HTTP GETs against a running FluxLit server.
# Usage:
#   ./scripts/run_smoke_app.sh
#   BASE_URL=http://127.0.0.1:8000 PATH_SUFFIX=/api/smoke COUNT=500 ./scripts/soak_http.sh
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PATH_SUFFIX="${PATH_SUFFIX:-/api/healthz}"
COUNT="${COUNT:-200}"
ok=0
fail=0
start=$SECONDS
for ((i = 1; i <= COUNT; i++)); do
  if curl -fsS "${BASE_URL}${PATH_SUFFIX}" >/dev/null; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
  fi
  if ((i % 50 == 0)); then
    echo "progress ${i}/${COUNT} ok=${ok} fail=${fail}"
  fi
done
elapsed=$((SECONDS - start))
echo "done ok=${ok} fail=${fail} elapsed_s=${elapsed}"
test "${fail}" -eq 0
