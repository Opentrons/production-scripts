BACKEND_DIR := backend
WEB_UI_DIR := web_ui
HOST ?= 0.0.0.0
BACKEND_PORT ?= 8100
WEB_UI_PORT ?= 8101
WEB_UI_BASE_PATH ?= /
WEB_UI_API_BASE_URL ?= /api

.PHONY: help install backend backend-prod health test web-ui-install web-ui-dev web-ui-build

help:
	@echo "Available targets:"
	@echo "  make install          Install backend dependencies with uv"
	@echo "  make backend          Start FastAPI backend with reload on port $(BACKEND_PORT)"
	@echo "  make backend-prod     Start FastAPI backend without reload"
	@echo "  make health           Check backend health endpoint"
	@echo "  make test             Run backend tests"
	@echo "  make web-ui-install   Install frontend dependencies"
	@echo "  make web-ui-dev       Start Vite frontend on port $(WEB_UI_PORT)"
	@echo "  make web-ui-build     Build frontend production assets"

install:
	cd $(BACKEND_DIR) && uv sync

backend:
	cd $(BACKEND_DIR) && uv run uvicorn app:app --host $(HOST) --port $(BACKEND_PORT) --reload

backend-prod:
	cd $(BACKEND_DIR) && uv run uvicorn app:app --host $(HOST) --port $(BACKEND_PORT)

health:
	curl -s http://127.0.0.1:$(BACKEND_PORT)/api/health

test:
	cd $(BACKEND_DIR) && uv run pytest -q tests

web-ui-install:
	cd $(WEB_UI_DIR) && npm ci

web-ui-dev:
	cd $(WEB_UI_DIR) && npm run dev -- --host $(HOST) --port $(WEB_UI_PORT)

web-ui-build:
	cd $(WEB_UI_DIR) && VITE_BASE_PATH=$(WEB_UI_BASE_PATH) VITE_API_BASE_URL=$(WEB_UI_API_BASE_URL) npm run build
