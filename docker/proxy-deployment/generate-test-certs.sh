#!/usr/bin/env bash
# Self-signed certs for docker/proxy-deployment TLS smoke tests (local + CI).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "$DIR"
if [[ -f "$DIR/cert.pem" && -f "$DIR/key.pem" ]]; then
  echo "Certs already present: $DIR"
  exit 0
fi
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -keyout "$DIR/key.pem" -out "$DIR/cert.pem" \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
echo "Wrote $DIR/cert.pem and key.pem"
