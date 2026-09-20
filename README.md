# t2-mobile

Учебный веб-портал оператора **t2** (ООО «Т2 Мобайл», ранее Tele2 Россия) для практической работы №2. Приложение запускается несколькими одинаковыми экземплярами, отдаёт идентификатор ноды в каждом ответе и готово к выносу за reverse-proxy Apache/Nginx в лабораторной работе №3.

Это не официальный сайт t2. Бренд, слоган «Другие правила. Новый уровень», линейка тарифов и факты о компании использованы как учебная тема.

## Что требуется работой №2 и как это закрыто

| Ограничение | Реализация |
|---|---|
| Видно, какая нода ответила | Заголовок `X-Backend-Instance`, страница `/status`, бейдж внизу каждой страницы, поле `handled_by` у платежей и обращений |
| Общее хранилище при падении ноды | PostgreSQL вынесен из приложения. `app-1` и `app-2` ходят в одну БД |
| Приложение не терминирует TLS | Uvicorn слушает только HTTP. Cookie `Secure` выключен |
| Сессии не в памяти и не в файлах | Redis, общий для всех инстансов |
| Несколько экземпляров за балансировщиком | `docker compose up` поднимает `app-1`, `app-2` и Nginx на `:8080` |
| Асинхронные запросы | FastAPI/async SQLAlchemy/Redis, `GET /api/v1/coverage/scan`, SSE `/api/v1/events` |
| Одновременный старт нод | Схема и демо-данные создаются под advisory-блокировкой PostgreSQL, старт ждёт БД и Redis с повторами |
| Быстрый отказ ноды | `proxy_connect_timeout 2s` + `proxy_next_upstream`: переключение на живую ноду за ~2 с |

## Практические работы курса

| Работа | Тема | Где лежит |
|---|---|---|
| №2 | Веб-приложение за балансировщиком | корень репозитория |
| №3 | Балансировка Nginx через Ansible | [`deploy/lab3/`](deploy/lab3/) |
| №4 | Docker Swarm | [`deploy/lab4/`](deploy/lab4/) |
| №5 | Portainer | [`deploy/lab5/`](deploy/lab5/) |
| №6 | Prometheus и Grafana | [`deploy/lab6/`](deploy/lab6/) |

У каждой работы свой README с командами запуска, объяснением решений и списком того,
что приложить к отчёту.

## Быстрый старт

Нужны Docker Desktop / Docker Engine и Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Откройте http://localhost:8080

Проверка, что балансировщик чередует ноды:

```bash
make instance-check
# или произвольное число запросов
./scripts/show-instances.sh http://localhost:8080/api/v1/instance 20
# или одним запросом
curl -sI http://localhost:8080/status | grep -i x-backend
```

Проверка отказоустойчивости: остановите одну ноду и обновите кабинет — сессия и баланс
останутся на месте, запросы уйдут на живую ноду.

```bash
docker compose stop app-1
./scripts/show-instances.sh
docker compose start app-1
```

Остановка:

```bash
docker compose down
```

### Демо-абоненты

| Телефон | PIN | Тариф |
|---|---|---|
| +7 900 123-45-67 | 1234 | Мой онлайн |
| +7 900 765-43-21 | 5678 | Безлимит |

## Что внутри

- Публичный сайт: тарифы, покрытие, о компании, поддержка
- Личный кабинет: баланс, пакеты, пополнение
- JSON API: `/api/docs`
- Идентичность инстанса: `/api/v1/instance`, `/status`
- Метрики Prometheus: `/api/metrics`, каждая серия помечена `instance_id`

Стек: FastAPI, Jinja2, PostgreSQL, Redis, Nginx (только локальный HTTP-прокси), Docker Compose.

Схема: [`docs/architecture.md`](docs/architecture.md)

## Разработка без Docker

PostgreSQL и Redis всё равно нужны (сессии и данные не должны жить в процессе приложения).

```bash
make install
# поднять postgres:16 и redis:7, затем
cp .env.example .env
make dev
```

Тесты и линтер:

```bash
make test
make lint
```

## Полезные URL

- http://localhost:8080/ — главная
- http://localhost:8080/status — какая нода ответила
- http://localhost:8080/api/health — liveness
- http://localhost:8080/api/ready — PostgreSQL + Redis
- http://localhost:8080/api/docs — OpenAPI
- http://localhost:8080/api/metrics — метрики Prometheus с меткой ноды

## Как это будут стыковать в работе №3

На VM `192.168.xx.12` и `.13` запускается этот сервис на `:8000`. На `.11` ставится Nginx, `upstream` указывает на обе ноды, TLS терминируется на балансировщике. Health-check балансировщика: `GET /api/health`.

Всё это автоматизировано в [`deploy/lab3/`](deploy/lab3/): инвентарь, плейбуки и шаблон
конфигурации, который подставляет адреса бэкендов сам и переключает метод балансировки
одной переменной.
