#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://localhost:8080/api/v1/instance}"

echo "Запросы к ${URL}"
echo "----------------------------------------"
for i in $(seq 1 12); do
  curl -sS --http1.1 -H 'Connection: close' -D - "$URL" -o /tmp/t2-instance-body.json | awk 'BEGIN{IGNORECASE=1} /^X-Backend-Instance:|^X-Backend-Hostname:|^HTTP\//'
  python3 -c 'import json,sys; print(json.load(open("/tmp/t2-instance-body.json"))["instance_id"])'
  echo
done
