.PHONY: dev down logs lint fmt test migrate-revision

dev:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

lint:
	cd backend && python -m ruff check app tests
	cd backend && python -m mypy app

fmt:
	cd backend && python -m ruff format app tests
	cd backend && python -m ruff check --fix app tests

test:
	cd backend && python -m pytest -q

migrate-revision:
	@echo "Generate migration: cd backend && alembic revision --autogenerate -m \"pesan\""
	@echo "Apply migration:    cd backend && alembic upgrade head"
