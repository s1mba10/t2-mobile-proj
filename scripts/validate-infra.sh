#!/usr/bin/env bash
# Проверяет артефакты лабораторных работ без виртуальных машин.
# Запуск: bash scripts/validate-infra.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-$ROOT/build/nginx}"
PY="${PY:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY=python3
fails=0

ok()   { printf '  OK    %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fails=$((fails + 1)); }
head2() { printf '\n== %s ==\n' "$1"; }

head2 "Ansible: синтаксис плейбуков"
for pb in "$ROOT"/deploy/lab3/playbooks/*.yml; do
  if (cd "$ROOT/deploy/lab3" && ansible-playbook "playbooks/$(basename "$pb")" --syntax-check >/dev/null 2>&1); then
    ok "$(basename "$pb")"
  else
    bad "$(basename "$pb")"
  fi
done

head2 "Nginx: конфигурация на версиях, которые стоят на виртуальных машинах"
"$PY" "$ROOT/scripts/render_nginx_template.py" "$OUT" >/dev/null || bad "отрисовка шаблона"
mkdir -p "$OUT/ssl"
[ -f "$OUT/ssl/t2.crt" ] || openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$OUT/ssl/t2.key" -out "$OUT/ssl/t2.crt" -days 2 -subj "/CN=t2.local" >/dev/null 2>&1
# 1.18 — Ubuntu 22.04, 1.24 — Ubuntu 24.04, 1.27 — актуальная ветка
for ver in 1.18-alpine 1.24-alpine 1.27-alpine; do
  bad_in_ver=0
  for conf in "$OUT"/*.conf; do
    docker run --rm \
      -v "$conf":/etc/nginx/nginx.conf:ro \
      -v "$OUT/ssl":/etc/nginx/ssl:ro \
      "nginx:$ver" nginx -t >/dev/null 2>&1 || bad_in_ver=$((bad_in_ver + 1))
  done
  if [ "$bad_in_ver" -eq 0 ]; then ok "nginx $ver"; else bad "nginx $ver ($bad_in_ver конфигураций)"; fi
done

head2 "Prometheus: конфигурация и правила"
if docker run --rm --entrypoint=promtool -v "$ROOT/deploy/lab6":/etc/prometheus \
    prom/prometheus:latest check config /etc/prometheus/prometheus.yml >/dev/null 2>&1; then
  ok "prometheus.yml"
else
  bad "prometheus.yml"
fi
if docker run --rm --entrypoint=promtool -v "$ROOT/deploy/lab6":/etc/prometheus \
    prom/prometheus:latest check rules /etc/prometheus/alerts.yml >/dev/null 2>&1; then
  ok "alerts.yml"
else
  bad "alerts.yml"
fi

head2 "Docker: файлы стеков и compose"
if docker compose -f "$ROOT/docker-compose.yml" config >/dev/null 2>&1; then
  ok "docker-compose.yml"
else
  bad "docker-compose.yml"
fi
if T2_DB_PASSWORD=validate T2_SECRET=validate \
   docker stack config -c "$ROOT/deploy/lab4/t2-stack.yml" >/dev/null 2>&1; then
  ok "lab4/t2-stack.yml"
else
  bad "lab4/t2-stack.yml"
fi
# Секрет должен доезжать до строки подключения целиком. Однажды сообщение
# об ошибке в подстановке содержало $( ) и compose подставил мусор: база
# получила один пароль, приложение другое, и это прошло stack config молча.
secret_probe=$(T2_DB_PASSWORD=probe123secret T2_SECRET=probe456 \
  docker stack config -c "$ROOT/deploy/lab4/t2-stack.yml" 2>/dev/null)
if printf '%s' "$secret_probe" | grep -q 'postgresql+asyncpg://t2:probe123secret@db' \
   && printf '%s' "$secret_probe" | grep -q 'POSTGRES_PASSWORD: probe123secret'; then
  ok "lab4: пароль одинаков в строке подключения и в базе"
else
  bad "lab4: пароль искажён при подстановке"
fi

if docker stack config -c "$ROOT/deploy/lab6/monitoring-stack.yml" >/dev/null 2>&1; then
  ok "lab6/monitoring-stack.yml"
else
  bad "lab6/monitoring-stack.yml"
fi
if docker stack config -c "$ROOT/deploy/lab5/portainer-agent-stack.yml" >/dev/null 2>&1; then
  ok "lab5/portainer-agent-stack.yml"
else
  bad "lab5/portainer-agent-stack.yml"
fi

head2 "Итог"
if [ "$fails" -eq 0 ]; then
  echo "  все проверки пройдены"
else
  echo "  провалов: $fails"
fi
exit "$fails"
