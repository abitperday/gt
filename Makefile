start:
	poetry run python main.py

web:
	poetry run python live_server.py

live:
	poetry run python live_server.py

graphs:
	poetry run python graphs.py $(SESSION)

migrate:
	poetry run alembic upgrade head

install:
	poetry install
	mkdir -p .run/storage/_data
	make migrate

test:
	poetry run pytest -s tests/

format:
	poetry run ruff format src/ tests/ main.py web.py live_server.py

mypy:
	poetry run mypy src/ main.py web.py live_server.py --check-untyped-defs

lint:
	poetry run ruff check src/ main.py web.py live_server.py

isort:
	poetry run isort src/ tests/ main.py web.py
