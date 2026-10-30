.PHONY: install infra migrate api worker chunks dataset reindex search calibrate index-data eval lint test

install:
	uv sync --frozen

infra:
	docker compose -p mortgage-assistant up -d --wait

migrate:
	uv run python -m app.core.migrate

api:
	uv run uvicorn app.main:app --reload --port 8000

worker:
	uv run python -m app.temporal_worker

chunks:
	uv run python -m app.services.documents $(FILE)

reindex:
	uv run python -m app.rag.reindex

search:
	uv run python -m app.rag.retrieval "$(Q)" $(MODE)

calibrate:
	uv run python -m app.rag.calibrate

index-data:
	for f in data/*; do curl -s -F "file=@$$f" localhost:8000/documents; echo; done

eval:
	uv run python -m evals.runner $(if $(FULL),--full,)

dataset:
	uv run python scripts/make_dataset.py

lint:
	uv run ruff check .

test:
	uv run pytest -q
