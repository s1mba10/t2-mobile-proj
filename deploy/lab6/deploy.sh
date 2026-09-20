#!/usr/bin/env bash
# Разворачивает стек мониторинга. Запускать на manager-ноде:
#   bash deploy/lab6/deploy.sh
set -euo pipefail

STACK="${STACK:-monitoring}"
NETWORK="${T2_NETWORK:-t2_t2net}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker node ls >/dev/null 2>&1 || {
  echo "Ошибка: узел не является manager-нодой Swarm." >&2
  exit 1
}

# Prometheus ходит за метриками приложения в сеть стека из работы №4.
# Если та работа ещё не развёрнута, сети нет и docker stack deploy падает
# с невнятным сообщением. Создаём пустую сеть с тем же именем:
# стек поднимется, а цель t2_app будет просто помечена как недоступная.
if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  echo "Сеть $NETWORK не найдена — стек работы №4 не развёрнут."
  echo "Создаю пустую overlay-сеть с этим именем, чтобы мониторинг поднялся."
  docker network create --driver overlay --attachable "$NETWORK" >/dev/null
fi

T2_NETWORK="$NETWORK" docker stack deploy -c "$HERE/monitoring-stack.yml" "$STACK"

echo
echo "Жду, пока сервисы поднимутся..."
for _ in $(seq 1 60); do
  ready=$(docker stack services "$STACK" --format '{{.Replicas}}' \
          | awk -F/ '$1 == $2 {n++} END {print n + 0}')
  total=$(docker stack services "$STACK" --format '{{.Replicas}}' | wc -l | tr -d ' ')
  echo "  готово сервисов: $ready из $total"
  [ "$ready" = "$total" ] && break
  sleep 5
done

docker stack services "$STACK"

ip=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
echo "Prometheus: http://${ip:-<адрес-менеджера>}:9090"
echo "Grafana:    http://${ip:-<адрес-менеджера>}:3000  (admin/admin)"
