# Практическая работа №3 — HAProxy и Keepalived

Отказоустойчивая схема балансировки: два узла HAProxy с Keepalived и плавающим адресом,
две активные ноды приложения из работы №2.

| Компонент | IP | FQDN |
|---|---|---|
| LoadBalancer #1 (MASTER) | 192.168.100.11 | shevkoplyas-lb.ivbo21.local |
| LoadBalancer #2 (BACKUP) | 192.168.100.12 | golubintsev-lb.ivbo21.local |
| Backend #1 | 192.168.100.21 | golubintsev.ivbo21.local |
| Backend #2 | 192.168.100.22 | golubintsev-b.ivbo21.local |
| Виртуальный адрес | 192.168.100.100 | site.ivbo21.local |

Адреса и имена правятся под реальную сеть в обоих конфигурационных файлах HAProxy
и в `keepalived-*.conf`.

## Состав

| Файл | Назначение |
|---|---|
| `haproxy/haproxy-tcp.cfg` | этап 4: режим tcp, алгоритм roundrobin |
| `haproxy/haproxy.cfg` | этапы 5–7: режим http, TLS, панель статистики |
| `keepalived/keepalived-master.conf` | VRRP, роль MASTER, priority 150 |
| `keepalived/keepalived-backup.conf` | VRRP, роль BACKUP, priority 100 |
| `keepalived/check_haproxy.sh` | скрипт для vrrp_script |

## Установка на балансировщики

```bash
sudo apt update && sudo apt install -y haproxy keepalived

sudo install -m 755 keepalived/check_haproxy.sh /etc/keepalived/check_haproxy.sh
sudo cp keepalived/keepalived-master.conf /etc/keepalived/keepalived.conf   # на LB1
sudo cp keepalived/keepalived-backup.conf /etc/keepalived/keepalived.conf   # на LB2

sudo mkdir -p /etc/haproxy/certs
sudo openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout /tmp/site.key -out /tmp/site.crt \
  -subj '/C=RU/ST=Moscow/L=Moscow/O=RTU MIREA/CN=site.ivbo21.local' \
  -addext 'subjectAltName=DNS:site.ivbo21.local,DNS:shevkoplyas-lb.ivbo21.local,DNS:golubintsev-lb.ivbo21.local,IP:192.168.100.100'
sudo sh -c 'cat /tmp/site.crt /tmp/site.key > /etc/haproxy/certs/site.ivbo21.local.pem'
sudo chmod 600 /etc/haproxy/certs/site.ivbo21.local.pem

sudo cp haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg
sudo haproxy -c -f /etc/haproxy/haproxy.cfg
sudo systemctl enable --now haproxy keepalived
```

Один и тот же сертификат кладётся на оба балансировщика: все имена и виртуальный адрес
перечислены в subjectAltName.

## Смена алгоритма балансировки

```bash
sudo sed -i 's/^    balance .*/    balance leastconn/' /etc/haproxy/haproxy.cfg
sudo haproxy -c -f /etc/haproxy/haproxy.cfg && sudo systemctl reload haproxy
```

Проверенные значения: `roundrobin`, `leastconn`, `source`.

## Что проверено локально

Обе конфигурации HAProxy проходят `haproxy -c` на версии 2.8 из состава Ubuntu 24.04
и на версии 3.0. Обе конфигурации Keepalived приняты `keepalived -t` версии 2.2.8.
Проверка выполнена без развёртывания стенда, на виртуальных машинах работу нужно
подтвердить вручную.
