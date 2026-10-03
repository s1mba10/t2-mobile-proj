#!/bin/bash
# Проверка живости HAProxy для vrrp_script.
# Код возврата 0 — процесс работает, иначе keepalived понизит приоритет узла
# и виртуальный адрес переедет на второй балансировщик.
pidof haproxy >/dev/null 2>&1 || exit 1
exit 0
