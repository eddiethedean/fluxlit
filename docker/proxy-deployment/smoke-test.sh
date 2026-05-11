#!/usr/bin/env bash
# Verify API + Streamlit shell (+ optional WebSocket) through nginx.
# Env:
#   BASE_URL       Public origin (default http://127.0.0.1:8080)
#   PUBLIC_PREFIX  Subpath (default /myapp)
#   CURL_INSECURE  If 1, curl uses -k (HTTPS with self-signed)
#   SKIP_WS        If 1, skip WebSocket handshake check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="${BASE_URL:-http://127.0.0.1:8080}"
BASE="${BASE%/}"
PREFIX="${PUBLIC_PREFIX-/myapp}"

# Avoid empty-array expansion under `set -u` (older bash).
_curl() {
  if [[ "${CURL_INSECURE:-}" == "1" ]]; then
    curl -k "$@"
  else
    curl "$@"
  fi
}

api_url="${BASE}${PREFIX}/api/healthz"
ready_url="${BASE}${PREFIX}/api/readyz"
smoke_url="${BASE}${PREFIX}/api/smoke"
request_id_url="${BASE}${PREFIX}/api/request-id"
root_url="${BASE}${PREFIX}/"

wait_curl() {
  local url=$1
  local desc=$2
  local n=0
  while [[ $n -lt 45 ]]; do
    if _curl -sfS --max-time 10 "$url" >/dev/null 2>&1; then
      return 0
    fi
    n=$((n + 1))
    sleep 2
  done
  echo "FAIL: timeout waiting for $desc ($url)"
  return 1
}

echo "Waiting for API: ${api_url}"
wait_curl "$api_url" "API health"

echo "Checking API JSON: ${api_url}"
api_out="$(_curl -sfS --max-time 30 "$api_url")"
echo "$api_out" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' \
  || { echo "FAIL: unexpected health JSON: $api_out"; exit 1; }
echo "API OK"

echo "Checking readiness: ${ready_url}"
wait_curl "$ready_url" "API readiness"
ready_out="$(_curl -sfS --max-time 30 "$ready_url")"
echo "$ready_out" | grep -q '"status"[[:space:]]*:[[:space:]]*"ready"' \
  || { echo "FAIL: unexpected readiness JSON: $ready_out"; exit 1; }
echo "Readiness OK"

echo "Checking smoke API: ${smoke_url}"
smoke_out="$(_curl -sfS --max-time 30 "$smoke_url")"
echo "$smoke_out" | grep -q '"marker"[[:space:]]*:[[:space:]]*"fluxlit_smoke_ok"' \
  || { echo "FAIL: unexpected smoke JSON: $smoke_out"; exit 1; }
echo "Smoke API OK"

echo "Checking request id header through proxy: ${request_id_url}"
rid="proxy-smoke-$RANDOM"
rid_out="$(_curl -sfS --max-time 30 -H "X-Request-ID: ${rid}" "$request_id_url")"
echo "$rid_out" | grep -q "\"request_id\"[[:space:]]*:[[:space:]]*\"${rid}\"" \
  || { echo "FAIL: request id not preserved: $rid_out"; exit 1; }
echo "Request ID OK"

echo "Waiting for Streamlit shell: ${root_url}"
wait_curl "$root_url" "gateway root"

echo "Checking Streamlit HTML: ${root_url}"
html="$(_curl -sfS --max-time 30 "$root_url")"
echo "$html" | grep -qiE 'streamlit|_stcore|stApp' \
  || { echo "FAIL: page does not look like Streamlit"; echo "$html" | head -c 500; exit 1; }
echo "Frontend shell OK"

echo "Checking oversized proxied body returns 413"
oversized_status="$(python3 - <<PY
import urllib.error
import urllib.request

url = "${root_url}oversized"
req = urllib.request.Request(url, data=b"x" * 256, method="POST")
try:
    urllib.request.urlopen(req, timeout=30)
    print("200")
except urllib.error.HTTPError as exc:
    print(exc.code)
PY
)"
[[ "$oversized_status" == "413" ]] \
  || { echo "FAIL: expected 413 for oversized proxy body, got ${oversized_status}"; exit 1; }
echo "Oversized body OK"

if [[ -z "${SKIP_WS:-}" ]]; then
  if ! python3 -c "import websockets" 2>/dev/null; then
    echo "FAIL: need Python package websockets (pip install websockets) or set SKIP_WS=1"
    exit 1
  fi
  if [[ "$BASE" == https://* ]]; then
    export WS_URL="wss://${BASE#https://}${PREFIX}/_stcore/stream"
  else
    export WS_URL="ws://${BASE#http://}${PREFIX}/_stcore/stream"
  fi
  echo "Checking WebSocket: ${WS_URL}"
  export CURL_INSECURE="${CURL_INSECURE:-}"
  python3 "$SCRIPT_DIR/smoke_ws.py"
fi

echo "All smoke checks passed."
