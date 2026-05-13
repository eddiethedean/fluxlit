#!/usr/bin/env bash
# Soak GET against the gateway Prometheus scrape path (default /__fluxlit/metrics).
#
# Prerequisites:
#   - FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS=1 on the FluxLit process
#   - prometheus-client installed (e.g. pip install -e ".[dev]" or fluxlit[metrics])
#
# Expected signals (see docs/runbooks.md, docs/observability.md):
#   - HTTP 200 and text exposition body containing stable metric family names
#     (e.g. fluxlit_gateway_requests_total) when metrics are enabled.
#   - HTTP 404 if metrics are disabled — fix env/install and retry.
#
# Usage:
#   FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS=1 ./scripts/run_smoke_app.sh   # terminal 1
#   COUNT=80 BASE_URL=http://127.0.0.1:8000 ./scripts/soak_metrics.sh
#
# Environment:
#   PATH_SUFFIX   default /__fluxlit/metrics (must match gateway_prometheus_metrics_path)
#   REQUIRE_BODY_SUBSTRING  default fluxlit_gateway_requests_total
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PATH_SUFFIX="${PATH_SUFFIX:-/__fluxlit/metrics}"
COUNT="${COUNT:-200}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-text}"
REQUIRE_BODY_SUBSTRING="${REQUIRE_BODY_SUBSTRING:-fluxlit_gateway_requests_total}"
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
  tmp="$(mktemp)"
  code="$(curl -sS -o "$tmp" -w "%{http_code}" "${BASE_URL}${PATH_SUFFIX}" || echo "000")"
  request_end_ns="$(python3 - <<'PY'
import time
print(time.perf_counter_ns())
PY
)"
  durations_ms+=("$(((request_end_ns - request_start_ns) / 1000000))")
  body_ok=0
  if [[ "$code" == "200" ]] && grep -q "${REQUIRE_BODY_SUBSTRING}" "$tmp" 2>/dev/null; then
    body_ok=1
  fi
  rm -f "$tmp"
  if [[ "$code" == "200" ]] && [[ "$body_ok" == "1" ]]; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
  fi
  if ((i % 50 == 0)); then
    echo "progress ${i}/${COUNT} ok=${ok} fail=${fail} last_http=${code}"
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

if [[ "$fail" -ne 0 ]]; then
  echo "soak_metrics: failures detected (enable FLUXLIT_ENABLE_GATEWAY_PROMETHEUS_METRICS=1 and install prometheus-client)" >&2
  exit 1
fi
