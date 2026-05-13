#!/usr/bin/env bash
# Lightweight soak: repeated HTTP GETs against a running FluxLit server.
# Uses curl -f: only HTTP 2xx counts as success (good for /api/healthz, /api/smoke).
#
# For readiness (/api/readyz) where 503 is meaningful, use scripts/soak_readyz.sh
# instead — see docs/runbooks.md and docs/deployment.md.
#
# Usage:
#   ./scripts/run_smoke_app.sh
#   BASE_URL=http://127.0.0.1:8000 PATH_SUFFIX=/api/smoke COUNT=500 ./scripts/soak_http.sh
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PATH_SUFFIX="${PATH_SUFFIX:-/api/healthz}"
COUNT="${COUNT:-200}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-text}" # text | json | markdown
ok=0
fail=0
start=$SECONDS
durations_ms=()
for ((i = 1; i <= COUNT; i++)); do
  request_start_ns="$(python3 - <<'PY'
import time
print(time.perf_counter_ns())
PY
)"
  if curl -fsS "${BASE_URL}${PATH_SUFFIX}" >/dev/null; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
  fi
  request_end_ns="$(python3 - <<'PY'
import time
print(time.perf_counter_ns())
PY
)"
  durations_ms+=("$(((request_end_ns - request_start_ns) / 1000000))")
  if ((i % 50 == 0)); then
    echo "progress ${i}/${COUNT} ok=${ok} fail=${fail}"
  fi
done
elapsed=$((SECONDS - start))

sorted_file="$(mktemp)"
trap 'rm -f "$sorted_file"' EXIT
printf '%s\n' "${durations_ms[@]}" | sort -n >"$sorted_file"
percentile_ms() {
  local p=$1
  local n
  n="$(wc -l <"$sorted_file" | tr -d ' ')"
  if ((n == 0)); then
    echo 0
    return
  fi
  python3 - "$p" "$n" <<'PY'
import sys
p = float(sys.argv[1])
n = int(sys.argv[2])
print(max(0, min(n - 1, round((n - 1) * p))))
PY
}
p50_ms="$(sed -n "$(( $(percentile_ms 0.50) + 1 ))p" "$sorted_file")"
p95_ms="$(sed -n "$(( $(percentile_ms 0.95) + 1 ))p" "$sorted_file")"
p99_ms="$(sed -n "$(( $(percentile_ms 0.99) + 1 ))p" "$sorted_file")"

case "$OUTPUT_FORMAT" in
  json)
    printf '{"base_url":"%s","path":"%s","count":%s,"ok":%s,"fail":%s,"elapsed_s":%s,"p50_ms":%s,"p95_ms":%s,"p99_ms":%s}\n' \
      "$BASE_URL" "$PATH_SUFFIX" "$COUNT" "$ok" "$fail" "$elapsed" "$p50_ms" "$p95_ms" "$p99_ms"
    ;;
  markdown)
    cat <<EOF
| base_url | path | count | ok | fail | elapsed_s | p50_ms | p95_ms | p99_ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ${BASE_URL} | ${PATH_SUFFIX} | ${COUNT} | ${ok} | ${fail} | ${elapsed} | ${p50_ms} | ${p95_ms} | ${p99_ms} |
EOF
    ;;
  *)
    echo "done ok=${ok} fail=${fail} elapsed_s=${elapsed} p50_ms=${p50_ms} p95_ms=${p95_ms} p99_ms=${p99_ms}"
    ;;
esac
test "${fail}" -eq 0
