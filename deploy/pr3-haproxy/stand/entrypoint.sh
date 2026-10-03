#!/bin/sh
# Запускает HAProxy в фоне и Keepalived на переднем плане.
# Так vrrp_script видит процесс HAProxy и реагирует на его остановку.
set -e
mkdir -p /run/haproxy
haproxy -f /etc/haproxy/haproxy.cfg -D -p /run/haproxy.pid
exec keepalived -n -l -D -f /etc/keepalived/keepalived.conf
