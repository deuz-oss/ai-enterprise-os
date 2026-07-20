.PHONY: dev down logs lint test fmt migrate

dev:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

lint:
	python -m ruff check services packages/python-common
	python -m mypy services packages/python-common/src
	npm run lint --if-present

test:
	python -m pytest -q
	npm run test --if-present

fmt:
	python -m black services packages/python-common
	python -m isort services packages/python-common
	npm run fmt --if-present

migrate:
	@echo "Alembic scaffold is service-owned. Use: cd services/<service> && uv run alembic upgrade head"