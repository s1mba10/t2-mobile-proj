#!/usr/bin/env bash
# Разворачивает стек практической работы №4 на Swarm-кластере.
# Запускать на manager-ноде из корня репозитория:
#   bash deploy/lab4/deploy.sh
set -euo pipefail

STACK="${STACK:-t2}"
REGISTRY="${REGISTRY:-127.0.0.1:5000}"
IMAGE="${IMAGE:-$REGISTRY/t2-mobile:lab4}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECRETS_FILE="${SECRETS_FILE:-$REPO_ROOT/deploy/lab4/.t2-secrets}"

step() { printf '\n==> %s\n' "$1"; }

# Секреты не лежат в репозитории: при первом запуске генерируются
# и сохраняются локально, при последующих переиспользуются.
if [ -f "$SECRETS_FILE" ]; then
  # shellcheck disable=SC1090
  . "$SECRETS_FILE"
else
  umask 077
  {
    echo "export T2_DB_PASSWORD=$(openssl rand -hex 16)"
    echo "export T2_SECRET=$(openssl rand -hex 32)"
  } > "$SECRETS_FILE"
  # shellcheck disable=SC1090
  . "$SECRETS_FILE"
  echo "Секреты сгенерированы и сохранены в $SECRETS_FILE"
fi
export T2_DB_PASSWORD T2_SECRET

step "Проверяю, что узел — manager"
docker node ls >/dev/null

step "Помечаю ноду для хранилища, если метки ещё нет"
node_id=$(docker node ls --filter role=manager --format '{{.ID}}' | head -1)
docker node update --label-add t2_role=storage "$node_id" >/dev/null
docker node inspect "$node_id" --format '    метки: {{.Spec.Labels}}'

step "Поднимаю локальный реестр образов"
if ! docker service ls --format '{{.Name}}' | grep -qx registry; then
  docker service create --name registry --publish published=5000,target=5000 \
    --constraint 'node.role == manager' registry:2 >/dev/null
  sleep 5
fi
docker service ls --filter name=registry --format '    реестр: {{.Name}} {{.Replicas}}'

step "Собираю образ приложения и кладу в реестр"
docker build -t "$IMAGE" "$REPO_ROOT" >/dev/null
docker push "$IMAGE" >/dev/null
echo "    образ: $IMAGE"

step "Разворачиваю стек $STACK"
T2_IMAGE="$IMAGE" docker stack deploy -c "$REPO_ROOT/deploy/lab4/t2-stack.yml" "$STACK"

step "Жду, пока реплики поднимутся"
for _ in $(seq 1 60); do
  running=$(docker service ps "${STACK}_app" --filter desired-state=running \
    --format '{{.CurrentState}}' | grep -c '^Running' || true)
  want=$(docker service inspect "${STACK}_app" --format '{{.Spec.Mode.Replicated.Replicas}}')
  echo "    запущено $running из $want"
  [ "$running" = "$want" ] && break
  sleep 5
done

step "Состояние стека"
docker stack services "$STACK"
docker service ps "${STACK}_app" --format 'table {{.Name}}\t{{.Node}}\t{{.CurrentState}}'
