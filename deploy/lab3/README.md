# Лабораторная работа №3 — балансировка нагрузки на Nginx через Ansible

Разворачивает портал t2 на трёх виртуальных машинах: балансировщик и два веб-сервера.
Адреса бэкендов подставляются в конфигурацию Nginx автоматически из инвентаря.

## Схема

```
                    клиент
                      │ HTTPS
              ┌───────▼────────┐
              │  node1  .11    │  Nginx: TLS-терминация и балансировка
              │  PostgreSQL    │  общее хранилище
              │  Redis         │
              └───┬────────┬───┘
            HTTP  │        │  HTTP
          ┌───────▼──┐  ┌──▼───────┐
          │ node2 .12│  │ node3 .13│  экземпляры приложения :8000
          └──────────┘  └──────────┘
```

PostgreSQL и Redis стоят на узле балансировщика, а не на веб-нодах. Если положить хранилище
на node2, её выключение унесёт данные всех нод и нарушит ограничение №2 практической работы №2.

## Подготовка

1. Заменить `xx` на номер подгруппы в `inventory/hosts.ini` и указать реальное имя
   пользователя в `ansible_user`.
2. Разложить ssh-ключ: `ssh-copy-id user@192.168.xx.11` и так для каждой ноды.
3. Проверить связность:

```bash
cd deploy/lab3
ansible all -m ping
```

## Запуск

```bash
ansible-playbook playbooks/site.yml
```

Плейбук ставит Docker, поднимает PostgreSQL и Redis, собирает образ приложения из репозитория
на каждой веб-ноде, затем настраивает Nginx и сразу делает шесть контрольных запросов,
показывая, какие ноды ответили.

Отдельные этапы:

```bash
ansible-playbook playbooks/setup_docker.yml
ansible-playbook playbooks/setup_storage.yml
ansible-playbook playbooks/setup_webservers.yml
ansible-playbook playbooks/setup_loadbalancer.yml
```

## Смена метода балансировки

Шаблон один, метод задаётся переменной. Правка конфигурации на сервере руками не нужна.

```bash
ansible-playbook playbooks/setup_loadbalancer.yml -e balance_method=round_robin
ansible-playbook playbooks/setup_loadbalancer.yml -e balance_method=least_conn
ansible-playbook playbooks/setup_loadbalancer.yml -e balance_method=ip_hash
ansible-playbook playbooks/setup_loadbalancer.yml -e balance_method=weighted
ansible-playbook playbooks/setup_loadbalancer.yml -e balance_method=cookie_hash
```

| Значение | Что делает | Что показать в отчёте |
|---|---|---|
| `round_robin` | по очереди, режим по умолчанию | строгое чередование node2 и node3 |
| `least_conn` | тому, у кого меньше активных соединений | под нагрузкой распределение смещается |
| `ip_hash` | клиент закреплён за нодой по IP | с одной машины всегда одна и та же нода |
| `weighted` | по весам из инвентаря, 3 к 1 | на node2 приходит втрое больше запросов |
| `cookie_hash` | привязка по cookie сессии | замена sticky, которой нет в открытой версии |

Директива `sticky` из методических указаний доступна только в NGINX Plus, поэтому для
липких сессий здесь используется `hash $cookie_t2_session consistent`.

Дополнительные переключатели: `-e enable_cache=true` включает кэш на балансировщике,
`-e enable_l7_split=true` — маршрутизацию по URI, `-e enable_tls=false` отключает HTTPS.

## Проверка работы

```bash
# чередование нод: заголовок X-Backend-Instance показывает, кто ответил
for i in $(seq 1 12); do curl -ks -o /dev/null -D - https://192.168.xx.11/api/v1/instance \
  | grep -i x-backend-instance; done

# то же самое готовым скриптом из репозитория
./scripts/show-instances.sh https://192.168.xx.11/api/v1/instance 20

# журнал балансировщика: видно адрес бэкенда для каждого запроса
ssh user@192.168.xx.11 'sudo tail -20 /var/log/nginx/access.log'

# встроенная статистика Nginx
ssh user@192.168.xx.11 'curl -s http://127.0.0.1/nginx-status'
```

Проверка отказоустойчивости:

```bash
ssh user@192.168.xx.12 'cd /opt/t2-mobile-app && docker compose stop'
curl -ks https://192.168.xx.11/api/v1/instance     # отвечает node3, сессия жива
ssh user@192.168.xx.12 'cd /opt/t2-mobile-app && docker compose start'
```

## Что вошло в конфигурацию

- **TLS-терминация** на балансировщике, самоподписанный сертификат выпускается плейбуком.
  Приложение слушает только HTTP — ограничение №3 практической работы №2 соблюдено.
- **Проверки состояния**: `max_fails=3 fail_timeout=15s`, `proxy_connect_timeout 2s`,
  `proxy_next_upstream`. Запрос к упавшей ноде уходит на живую за две секунды.
- **Журнал с адресом бэкенда** — готовый материал для отчёта.
- **Отдельный location для потока событий** без буферизации.
- **Кэширование** и **маршрутизация по URI** — опциональные блоки.

## Что приложить к отчёту

1. Вывод `ansible-playbook playbooks/site.yml` (последние строки с идентификаторами нод).
2. Скриншот сайта по адресу балансировщика с видимой плашкой «Ответ от ноды».
3. Вывод `curl` или скрипта на 12–20 запросов для round-robin.
4. То же для двух других методов, например `least_conn` и `ip_hash`.
5. Фрагмент `/var/log/nginx/access.log` со столбцом адреса бэкенда.
6. Демонстрация отказа: остановленная нода и продолжающий работать портал.

## Проверка без виртуальных машин

Синтаксис плейбуков и валидность генерируемой конфигурации проверяются локально:

```bash
cd deploy/lab3
ansible-playbook playbooks/site.yml --syntax-check
```

Шаблон отрисован и проверен командой `nginx -t` для всех пяти методов балансировки,
а также для вариантов с кэшем, маршрутизацией по URI и без TLS.
