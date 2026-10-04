# ═══════════════════════════════════════════════════════════════════════════
# NEXUS AI SWARM PLATFORM — Makefile
# ═══════════════════════════════════════════════════════════════════════════
SHELL := /bin/bash
.DEFAULT_GOAL := help

PY       := python3
BACKEND   = backend
FRONTEND  = frontend
VENV     := $(BACKEND)/.venv

.PHONY: help install install-backend install-frontend dev-backend dev-frontend \
        test lint typecheck build docker-build docker-up docker-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install backend + frontend dependencies

install-backend: ## Create venv and install backend dependencies
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r $(BACKEND)/requirements.txt -r $(BACKEND)/requirements-dev.txt

install-frontend: ## Install frontend dependencies
	cd $(FRONTEND) && npm install

dev-backend: ## Run the FastAPI backend with hot reload (port 8000)
	cd $(BACKEND) && $(VENV)/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Run the Vite dev server (port 5173, proxies /api -> :8000)
	cd $(FRONTEND) && npm run dev -- --host 0.0.0.0 --port 5173

test: ## Run the backend test suite
	cd $(BACKEND) && $(VENV)/bin/pytest -q

lint: ## Lint the backend with ruff
	cd $(BACKEND) && $(VENV)/bin/ruff check app tests

typecheck: ## Static type-check the frontend
	cd $(FRONTEND) && npm run typecheck

build: ## Build the production frontend bundle
	cd $(FRONTEND) && npm run build

docker-build: ## Build all container images
	docker compose build

docker-up: ## Start the full stack with Docker Compose
	docker compose up -d

docker-down: ## Stop the stack and remove volumes
	docker compose down -v

clean: ## Remove caches, build artifacts and runtime data
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache $(FRONTEND)/dist \
		$(FRONTEND)/node_modules/.vite workspace data
