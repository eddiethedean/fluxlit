#!/usr/bin/env bash
# Soak GET against readiness (default /api/readyz): records HTTP status + latency.
#
# Expected signals (see docs/runbooks.md, docs/deployment.md):
#   - HTTP 200 when the unified runtime has a healthy Streamlit upstream (readyz probe passes).
#   - HTTP 503 when the sidecar is down or misconfigured (same semantics as production probes).
#
# Unlike soak_http.sh, this script does NOT use curl -f, so 503 responses are counted
# rather than aborting the request loop.
#
# Usage:
#   ./scripts/run_smoke_app.sh   # terminal 1
#   BASE_URL=http://127.0.0.1:8000 COUNT=200 ./scripts/soak_readyz.sh
#
# Optional: PATH_SUFFIX=/api/readyz (default). REQUIRE_2XX=1 (default) fails if any
# response is not 2xx; set REQUIRE_2XX=0 to only emit a summary for investigations.
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PATH_SUFFIX="${PATH_SUFFIX:-/api/readyz}"
COUNT="${COUNT:-200}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-text}"
REQUIRE_2XX="${REQUIRE_2XX:-1}"

ok=0
fail=0
start=$SECONDS
durations_ms=()
declare -A code_counts=()

for ((i = 1; i <= COUNT; i++)); do
  request_start_ns="$(python3 - <<'PY'
import time
print(time.perf_counter_ns())
PY
)"
  code="$(curl -sS -o /dev/null -w "%{http_code}" "${BASE_URL}${PATH_SUFFIX}" || echo "000")"
  request_end_ns="$(python3 - <<'PY'
import time
print(time.perf_counter_ns())
PY
)"
  durations_ms+=("$(((request_end_ns - request_start_ns) / 1000000))")
  if [[ "$code" =~ ^2 ]]; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
  fi
  code_counts[$code]=$((${code_counts[$code]:-0} + 1))
  if ((i % 50 == 0)); then
    echo "progress ${i}/${COUNT} ok_2xx=${ok} other=${fail} last_http=${code}"
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

codes_line=""
for k in $(printf '%s\n' "${!code_counts[@]}" | sort -n); do
  codes_line="${codes_line}${k}=${code_counts[$k]} "
done

codes_json="$(printf '%s\n' "${!code_counts[@]}" | while read -r c; do echo "$c ${code_counts[$c]}"; done | python3 -c "import sys, json
d = {}
for line in sys.stdin:
    parts = line.strip().split()
    if len(parts) >= 2:
        d[parts[0]] = int(parts[1])
print(json.dumps(d))")"

case "$OUTPUT_FORMAT" in
  json)
    printf '{"base_url":"%s","path":"%s","count":%s,"ok_2xx":%s,"fail_non2xx":%s,"elapsed_s":%s,"p50_ms":%s,"p95_ms":%s,"p99_ms":%s,"http_codes":%s}\n' \
      "$BASE_URL" "$PATH_SUFFIX" "$COUNT" "$ok" "$fail" "$elapsed" "$p50_ms" "$p95_ms" "$p99_ms" "$codes_json"
    ;;
  markdown)
    echo "| base_url | path | count | ok_2xx | fail_non2xx | elapsed_s | p50_ms | p95_ms | p99_ms | http_codes |"
    echo "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"
    echo "| ${BASE_URL} | ${PATH_SUFFIX} | ${COUNT} | ${ok} | ${fail} | ${elapsed} | ${p50_ms} | ${p95_ms} | ${p99_ms} | ${codes_line} |"
    ;;
  *)
    echo "done ok_2xx=${ok} fail_non2xx=${fail} elapsed_s=${elapsed} p50_ms=${p50_ms} p95_ms=${p95_ms} p99_ms=${p99_ms} http_codes: ${codes_line}"
    ;;
esac

if [[ "$REQUIRE_2XX" == "1" ]] && [[ "$fail" -ne 0 ]]; then
  echo "soak_readyz: non-2xx responses detected (set REQUIRE_2XX=0 to ignore)" >&2
  exit 1
fi
