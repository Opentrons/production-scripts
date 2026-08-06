BACKEND_DIR := backend
WEB_UI_DIR := web_ui
HOST ?= 0.0.0.0
BACKEND_PORT ?= 8100
WEB_UI_PORT ?= 8101
WEB_UI_BASE_PATH ?= /
WEB_UI_API_BASE_URL ?= /api

.PHONY: help install backend backend-stop backend-prod health test web-ui-install web-ui-dev web-ui-build remote-chrome remote-chrome-status

help:
	@echo "Available targets:"
	@echo "  make install          Install backend dependencies with uv"
	@echo "  make backend          Restart FastAPI backend with reload on port $(BACKEND_PORT)"
	@echo "  make backend-stop     Stop the process listening on port $(BACKEND_PORT)"
	@echo "  make backend-prod     Start FastAPI backend without reload"
	@echo "  make health           Check backend health endpoint"
	@echo "  make test             Run backend tests"
	@echo "  make web-ui-install   Install frontend dependencies"
	@echo "  make web-ui-dev       Start Vite frontend on port $(WEB_UI_PORT)"
	@echo "  make web-ui-build     Build frontend production assets"
	@echo "  make remote-chrome    Start dedicated Chrome with CDP on port $(REMOTE_CHROME_PORT)"
	@echo "  make remote-chrome-status  Check the Chrome CDP endpoint"

install:
	cd $(BACKEND_DIR) && uv sync

backend-stop:
	@pids="$$(lsof -tiTCP:$(BACKEND_PORT) -sTCP:LISTEN 2>/dev/null)"; \
	if [ -n "$$pids" ]; then \
		echo "Stopping backend on port $(BACKEND_PORT) (PID: $$(echo $$pids | tr '\n' ' '))..."; \
		kill $$pids 2>/dev/null || true; \
		attempt=0; \
		while lsof -tiTCP:$(BACKEND_PORT) -sTCP:LISTEN >/dev/null 2>&1 && [ $$attempt -lt 5 ]; do \
			sleep 1; \
			attempt=$$((attempt + 1)); \
		done; \
		remaining="$$(lsof -tiTCP:$(BACKEND_PORT) -sTCP:LISTEN 2>/dev/null)"; \
		if [ -n "$$remaining" ]; then \
			echo "Force stopping backend on port $(BACKEND_PORT)..."; \
			kill -9 $$remaining 2>/dev/null || true; \
		fi; \
	else \
		echo "No backend process is listening on port $(BACKEND_PORT)."; \
	fi

backend: backend-stop
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

REMOTE_CHROME_PORT ?= 9222

remote-chrome:
	cd $(BACKEND_DIR) && DURO_REMOTE_CHROME_PORT=$(REMOTE_CHROME_PORT) ./scripts/start_duro_remote_chrome.sh

remote-chrome-status:
	curl -sS http://127.0.0.1:$(REMOTE_CHROME_PORT)/json/version
