.PHONY: help install dev up down logs test lint fmt demo instance-check validate

help:
	@echo "t2-mobile — команды разработки"
	@echo "  make install         установить зависимости"
	@echo "  make up              поднять 2 инстанса + Postgres + Redis + Nginx"
	@echo "  make down            остановить стек"
	@echo "  make logs            логи приложения"
	@echo "  make test            запустить тесты"
	@echo "  make demo            показать, что запросы ходят на разные ноды"
	@echo "  make instance-check  12 запросов к /api/v1/instance"
	@echo "  make validate        проверить артефакты лабораторных работ"

install:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e ".[dev]"

dev:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f app-1 app-2

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check app tests

validate:
	bash scripts/validate-infra.sh

fmt:
	.venv/bin/ruff check --fix app tests
	.venv/bin/ruff format app tests

demo: instance-check

instance-check:
	@chmod +x scripts/show-instances.sh
	@./scripts/show-instances.sh
