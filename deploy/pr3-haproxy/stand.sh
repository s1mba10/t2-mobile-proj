#!/usr/bin/env bash
# Управление стендом практической работы №3.
# Запускать из каталога deploy/pr3-haproxy:  bash stand.sh <команда>
set -euo pipefail
cd "$(dirname "$0")/stand"
C="docker compose"

case "${1:-help}" in

  up)        $C up -d --build; echo "Стенд поднят. Проверка: bash stand.sh status" ;;
  down)      $C down -v ;;
  status)    $C ps --format 'table {{.Name}}\t{{.Status}}' ;;

  vip)       # кто сейчас держит виртуальный адрес
             for n in lb1 lb2; do
               printf '%-4s ' "$n"
               $C exec -T $n sh -c 'ip -4 addr show dev eth0 | grep -q 192.168.100.100 \
                 && echo "держит VIP 192.168.100.100" || echo "в резерве"'
             done ;;

  nodes)     # какая нода отвечает: серия запросов через виртуальный адрес
             n=${2:-10}
             for i in $(seq 1 "$n"); do
               curl -ks -D - --resolve site.ivbo21.local:443:127.0.0.1 \
                 https://site.ivbo21.local/api/v1/instance -o /dev/null \
                 | grep -i x-served-by | tr -d '\r'
             done ;;

  algo)      # смена алгоритма балансировки: roundrobin | leastconn | source
             a=${2:?укажите алгоритм: roundrobin, leastconn или source}
             # Файл примонтирован в контейнеры, поэтому правим его на месте через cat:
             # sed -i подменил бы inode, и контейнеры видели бы старый файл.
             tmp=$(mktemp)
             sed "s/^    balance .*/    balance $a/" ../haproxy/haproxy.cfg > "$tmp"
             cat "$tmp" > ../haproxy/haproxy.cfg
             rm -f "$tmp"
             $C exec -T lb1 haproxy -c -f /etc/haproxy/haproxy.cfg >/dev/null
             $C restart lb1 lb2 >/dev/null 2>&1
             sleep 12
             echo "Алгоритм переключён на $a"
             $C exec -T lb1 grep -E "^    balance" /etc/haproxy/haproxy.cfg ;;

  fail)      # имитация отказа: гасим HAProxy на том узле, который держит VIP
             $C exec -T lb1 pkill haproxy && echo "HAProxy на lb1 остановлен" ;;

  restore)   $C exec -T lb1 sh -c 'haproxy -f /etc/haproxy/haproxy.cfg -D -p /run/haproxy.pid' \
             && echo "HAProxy на lb1 запущен" ;;

  log)       $C logs --no-color --since "${2:-2m}" lb1 lb2 | grep -iE 'script|priority|MASTER|BACKUP' ;;

  stats)     curl -s -u admin:admin123 --resolve site.ivbo21.local:8043:127.0.0.1 \
               "http://site.ivbo21.local:8043/stats;csv" \
             | awk -F, 'NR>1 && $2!="" {printf "%-14s %-12s %s\n", $1, $2, $18}' ;;

  *) cat <<'HLP'
Команды:
  up        поднять стенд
  status    состояние контейнеров
  vip       кто держит виртуальный адрес
  nodes N   N запросов через VIP, видно отвечающую ноду
  algo X    сменить алгоритм: roundrobin | leastconn | source
  fail      остановить HAProxy на основном балансировщике
  restore   вернуть HAProxy
  log       записи keepalived о смене состояния
  stats     состояние frontend/backend из панели статистики
  down      погасить стенд
HLP
  ;;
esac
