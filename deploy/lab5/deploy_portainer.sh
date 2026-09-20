#!/usr/bin/env bash
# Практическая работа №5: Portainer на manager-ноде Swarm-кластера.
# Запускать на 192.168.xx.11:  bash deploy/lab5/deploy_portainer.sh
set -euo pipefail

NAME="${NAME:-portainer}"
PORT="${PORT:-9000}"

if ! docker node ls >/dev/null 2>&1; then
  echo "Ошибка: узел не является manager-нодой Swarm." >&2
  exit 1
fi

if docker service ls --format '{{.Name}}' | grep -qx "$NAME"; then
  echo "Сервис $NAME уже существует, обновляю образ."
  docker service update --image portainer/portainer-ce:latest "$NAME"
  exit 0
fi

docker service create \
  --name "$NAME" \
  --replicas=1 \
  --publish "${PORT}:9000" \
  --constraint 'node.role == manager' \
  --mount type=volume,source=portainer_data,target=/data \
  --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock \
  portainer/portainer-ce:latest \
  -H unix:///var/run/docker.sock

echo
echo "Portainer разворачивается. Интерфейс будет доступен через минуту:"
ip=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "  http://${ip:-<адрес-менеджера>}:${PORT}"
echo "При первом входе создайте учётную запись администратора."
