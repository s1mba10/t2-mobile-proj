#!/usr/bin/env python3
"""Отрисовывает шаблон конфигурации балансировщика во все поддерживаемые варианты.

Нужен для проверки: сгенерированный конфиг потом прогоняется через nginx -t
на тех версиях nginx, которые реально стоят на виртуальных машинах.
"""
from __future__ import annotations

import pathlib
import sys

import yaml
from jinja2 import Environment, FileSystemLoader

LAB3 = pathlib.Path(__file__).resolve().parent.parent / "deploy" / "lab3"

GROUPS = {"webservers": ["node2", "node3"], "storage": ["node1"], "balancer": ["node1"]}
HOSTVARS = {
    "node1": {"ansible_host": "192.168.10.11"},
    "node2": {"ansible_host": "192.168.10.12", "nginx_weight": 3},
    "node3": {"ansible_host": "192.168.10.13", "nginx_weight": 1},
}

CASES: list[tuple[str, dict]] = [
    *[(m, {"balance_method": m}) for m in
      ("round_robin", "least_conn", "ip_hash", "weighted", "cookie_hash")],
    ("no_tls", {"balance_method": "round_robin", "enable_tls": False}),
    ("cache", {"balance_method": "round_robin", "enable_cache": True}),
    ("l7_split", {"balance_method": "round_robin", "enable_l7_split": True}),
]


def main(out_dir: str) -> int:
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    base = yaml.safe_load((LAB3 / "group_vars" / "all.yml").read_text())
    base.setdefault("postgres_password", "placeholder")
    base.setdefault("secret_key", "placeholder")

    env = Environment(
        loader=FileSystemLoader(str(LAB3 / "templates")), keep_trailing_newline=True
    )
    template = env.get_template("nginx.conf.j2")

    for name, overrides in CASES:
        variables = {**base, **overrides}
        text = template.render(
            groups=GROUPS, hostvars=HOSTVARS, inventory_hostname="node1", **variables
        )
        # В образах nginx нет пользователя www-data, для проверки синтаксиса
        # подставляем того, который в образе есть.
        (out / f"{name}.conf").write_text(text.replace("user www-data;", "user nginx;"))

    print(f"отрисовано вариантов: {len(CASES)} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "build/nginx"))
