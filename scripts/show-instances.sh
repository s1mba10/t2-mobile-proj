#!/usr/bin/env bash
# Показывает, какая нода backend ответила на каждый запрос через балансировщик.
# Заголовки разбираем grep -i: awk IGNORECASE есть только в gawk, на macOS его нет.
set -euo pipefail

URL="${1:-http://localhost:8080/api/v1/instance}"
COUNT="${2:-12}"

body=$(mktemp)
trap 'rm -f "$body"' EXIT

header() {
  printf '%s\n' "$1" | grep -i "^$2:" | head -1 | cut -d: -f2- | tr -d ' \r'
}

echo "Запросы к ${URL} (${COUNT} шт.)"
echo "--------------------------------------------------------"

tally=""
for i in $(seq 1 "$COUNT"); do
  headers=$(curl -sS --http1.1 -H 'Connection: close' -D - "$URL" -o "$body")
  status=$(printf '%s\n' "$headers" | grep -i '^HTTP/' | head -1 | tr -d '\r')
  instance=$(header "$headers" 'X-Backend-Instance')
  host=$(header "$headers" 'X-Backend-Hostname')
  printf '%2d  %-14s instance=%-10s host=%s\n' "$i" "$status" "${instance:-?}" "${host:-?}"
  tally="${tally}${instance:-?}"$'\n'
done

echo "--------------------------------------------------------"
echo "Распределение запросов по нодам:"
printf '%s' "$tally" | grep -v '^$' | sort | uniq -c | sed 's/^/  /'
