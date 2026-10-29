# Common tasks. Run `make help` for the list.

BACKEND := cd backend && uv run

.PHONY: help setup test lint format api web samples eval up down clean

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

setup: ## Install backend (uv) and frontend (npm) dependencies
	cd backend && uv sync
	cd frontend && npm ci

test: ## Run backend and frontend tests (no model download needed)
	$(BACKEND) pytest -q
	cd frontend && npx vitest run

lint: ## Lint and type-check everything
	cd backend && uv run ruff check . ../scripts ../eval --config pyproject.toml
	cd backend && uv run ruff format --check . ../scripts ../eval --config pyproject.toml
	cd frontend && npx tsc --noEmit

format: ## Auto-format Python code
	cd backend && uv run ruff format . ../scripts ../eval --config pyproject.toml

api: ## Run the API on :8000 (data in backend/data)
	$(BACKEND) galeria serve --reload

web: ## Run the frontend dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

samples: ## Download the eval sample set from Wikimedia Commons (~76 MB, checksummed)
	backend/.venv/bin/python scripts/download_samples.py

eval: ## Index the samples and run the eval (writes eval/results/latest.md)
	$(BACKEND) python ../eval/run_eval.py

up: ## Build and start the Docker stack on http://localhost:8080
	docker compose up --build -d

down: ## Stop the Docker stack (volumes are kept)
	docker compose down

clean: ## Remove local indexes and build output (keeps samples/)
	rm -rf data backend/data frontend/dist
