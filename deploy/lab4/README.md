# Лабораторная работа №4 — Docker Swarm

Разворачивает портал t2 в кластере Swarm: три реплики приложения по одной на ноду
и по одной реплике PostgreSQL и Redis, закреплённых за конкретной нодой.

## Подготовка кластера

На manager-ноде `192.168.xx.11`:

```bash
docker swarm init --advertise-addr 192.168.xx.11
```

Команду `docker swarm join`, которую выведет Swarm, выполнить на `192.168.xx.12` и `.13`:

```bash
docker swarm join --token <токен> 192.168.xx.11:2377
```

Проверка:

```bash
docker node ls          # должны быть видны три ноды в состоянии Ready
```

Пометить ноду, на которой будет жить база:

```bash
docker node update --label-add t2_role=storage node1
```

## Развёртывание

```bash
git clone https://github.com/s1mba10/t2-mobile-proj.git
cd t2-mobile-proj
bash deploy/lab4/deploy.sh
```

Скрипт помечает ноду, поднимает локальный реестр образов, собирает образ приложения,
кладёт его в реестр и разворачивает стек. Реестр нужен потому, что образ должен быть
доступен всем трём нодам, а не только той, где он собран.

Вручную то же самое:

```bash
docker service create --name registry --publish published=5000,target=5000 \
  --constraint 'node.role == manager' registry:2
docker build -t 127.0.0.1:5000/t2-mobile:lab4 .
docker push 127.0.0.1:5000/t2-mobile:lab4
docker stack deploy -c deploy/lab4/t2-stack.yml t2
```

## Проверка по пунктам задания

### 1–2. Три реплики веб-сервера и одна реплика БД

```bash
docker stack ls
docker stack services t2
docker service ps t2_app --format 'table {{.Name}}\t{{.Node}}\t{{.CurrentState}}'
docker service ps t2_db
```

Ожидается `t2_app 3/3`, по одной задаче на каждой из трёх нод, и `t2_db 1/1`.
Разъезд по нодам обеспечивает `placement.max_replicas_per_node: 1`.

Какая нода ответила, видно без захода на сервер:

```bash
curl -s http://192.168.xx.11/api/v1/instance
```

Поле `instance_id` заполняется шаблоном Swarm `{{.Node.Hostname}}-{{.Task.Slot}}`,
то есть содержит имя ноды и номер слота. Та же строка показана внизу каждой страницы сайта.

### 3. Отказоустойчивость

```bash
# выключить ноду node3 целиком либо перевести её в drain
docker node update --availability drain node3

docker service ps t2_app          # задача с node3 переехала на живую ноду
curl -s http://192.168.xx.13/     # по IP выключенной ВМ ответа нет
curl -s http://192.168.xx.11/     # через живую ноду портал работает
```

Зафиксировать в отчёте: ingress-сеть Swarm принимает запрос на любой живой ноде и
перенаправляет его на работающую реплику. Обращение по адресу выключенной машины
не проходит, потому что на ней некому принять соединение.

Самовосстановление проверяется убийством контейнера:

```bash
docker rm -f $(docker ps --filter name=t2_app --format '{{.ID}}' | head -1)
docker service ls --filter name=t2_app      # Swarm поднимает замену за несколько секунд
```

### 4. Закрепление базы данных за конкретной нодой

В файле стека у сервисов `db` и `redis`:

```yaml
deploy:
  placement:
    constraints:
      - "node.labels.t2_role == storage"
```

Три рабочих способа, от более гибкого к более жёсткому:

| Способ | Запись | Когда удобен |
|---|---|---|
| Метка ноды | `node.labels.t2_role == storage` | роль можно перенести на другую ноду одной командой |
| Имя ноды | `node.hostname == node1` | когда нода ровно одна и навсегда |
| Роль в кластере | `node.role == manager` | быстрый вариант без подготовки меток |

Переопределить без правки файла:

```bash
T2_DB_CONSTRAINT='node.hostname == node1' docker stack deploy -c deploy/lab4/t2-stack.yml t2
```

Проверка:

```bash
docker service inspect t2_db --format '{{.Spec.TaskTemplate.Placement.Constraints}}'
docker service ps t2_db --format '{{.Name}} -> {{.Node}}'
```

### 5. Масштабирование до пяти реплик

```bash
docker service scale t2_app=5
```

**Важно.** При `max_replicas_per_node: 1` и трёх нодах запустятся только три реплики,
остальные две останутся в состоянии `Pending` с ошибкой `no suitable node (max replicas per node limit exceed)`.
Это не сбой, а работающее ограничение размещения. Чтобы пять реплик действительно поднялись,
нужно разрешить по две на ноду:

```bash
T2_MAX_PER_NODE=2 T2_REPLICAS=5 docker stack deploy -c deploy/lab4/t2-stack.yml t2
docker service ls --filter name=t2_app
```

В отчёте имеет смысл показать оба состояния: сначала `2/5` или `3/5` с объяснением причины,
затем `5/5` после снятия ограничения.

### 6. Мониторинг состояния

```bash
docker node ls
docker stack ls
docker stack services t2
docker service ps t2_app
docker node ps node1
docker service logs t2_app --tail 20
```

## Пошаговое обновление и откат

```bash
docker service update --image 127.0.0.1:5000/t2-mobile:v2 t2_app
docker service inspect t2_app --format '{{.UpdateStatus.State}}'
docker service rollback t2_app
```

Параметры обновления заданы в стеке: `parallelism: 1`, `delay: 10s`, `order: stop-first`
и `failure_action: rollback`. Реплики обновляются по одной, при провале Swarm откатывается сам.

**Почему `stop-first`, а не `start-first`.** При `start-first` Swarm поднимает новую задачу
раньше, чем гасит старую, и на время обновления на ноде оказывается две реплики вместо одной.
Вместе с `max_replicas_per_node: 1` это приводит к вечному ожиданию: новая задача висит в
`Pending` с ошибкой `no suitable node (max replicas per node limit exceed)`, а обновление
никогда не завершается. Проверено на практике, поэтому в стеке стоит `stop-first`.
Кратковременная недоступность одной реплики не видна пользователю: остальные две продолжают
принимать запросы через ingress.

## Удаление

```bash
docker stack rm t2
docker service rm registry
```

## Что приложить к отчёту

1. `docker node ls` с тремя нодами.
2. `docker stack services t2` с `3/3` у приложения и `1/1` у базы.
3. `docker service ps t2_app` с распределением по трём нодам.
4. Ответ `curl` с `instance_id`, содержащим имя ноды.
5. Вывод до и после `docker node update --availability drain node3`.
6. `docker service inspect t2_db` с ограничением размещения.
7. Масштабирование до пяти реплик с объяснением ограничения.
8. Вывод `docker service logs t2_app`.

## Что проверено локально

Файл стека развёрнут на одноузловом Swarm: шаблон `{{.Node.Hostname}}-{{.Task.Slot}}`
подставляется, ingress распределяет запросы между репликами, ограничение размещения базы
работает, Swarm восстанавливает убитую реплику за три секунды, пошаговое обновление проходит.
