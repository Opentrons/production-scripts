BACKEND_DIR := backend
WEB_UI_DIR := web_ui
HOST ?= 0.0.0.0
PORT ?= 8090
WEB_UI_BASE_PATH ?= /
COMPONENT ?= all
DEPLOY_HOST ?=
PUSH_ARGS ?=
WEB_PUSH_ARGS ?=

BACKEND_PUSH_ARGS := $(PUSH_ARGS)
WEB_UI_PUSH_ARGS := $(WEB_PUSH_ARGS)
ifneq ($(DEPLOY_HOST),)
BACKEND_PUSH_ARGS += --host $(DEPLOY_HOST)
WEB_UI_PUSH_ARGS += --host $(DEPLOY_HOST)
endif

.PHONY: help install stop-backend backend backend-prod health \
	push push-all update update-all \
	push-backend update-backend web-ui-build push-web-ui update-web-ui

help:
	@echo "Available targets:"
	@echo "  make install       Install backend dependencies with uv"
	@echo "  make stop-backend  Stop backend service on PORT (default 8090)"
	@echo "  make backend       Start backend service with reload"
	@echo "  make backend-prod  Start backend service without reload"
	@echo "  make health        Check backend health endpoint"
	@echo "  make update        Update remote code (default: backend + web_ui)"
	@echo "  make push          Alias of update"
	@echo "  make push-backend  Upload backend code (stops service first, fixes robot_key)"
	@echo "  make update-backend Alias of push-backend"
	@echo "  make web-ui-build  Build web_ui dist"
	@echo "  make push-web-ui   Build and upload web_ui dist"
	@echo "  make update-web-ui Alias of push-web-ui"
	@echo ""
	@echo "Update parameters:"
	@echo "  COMPONENT=all|backend|web   Which part to update (default: all)"
	@echo "  DEPLOY_HOST=IP              Apply --host to both push scripts"
	@echo "  PUSH_ARGS='...'             Extra args for backend push-scripts.py"
	@echo "  WEB_PUSH_ARGS='...'         Extra args for web_ui push-scripts.py"
	@echo "  WEB_UI_BASE_PATH=/          Vite base path for web_ui build"
	@echo ""
	@echo "Examples:"
	@echo "  make update"
	@echo "  make update COMPONENT=backend"
	@echo "  make update COMPONENT=web"
	@echo "  make update DEPLOY_HOST=192.168.0.137"
	@echo "  make update PUSH_ARGS='--no-deploy' WEB_PUSH_ARGS='--no-deploy'"

install:
	cd $(BACKEND_DIR) && uv sync

stop-backend:
	@pkill -f "uvicorn app:app" 2>/dev/null || true
	@-lsof -ti :$(PORT) | xargs kill -9 2>/dev/null || true

backend: stop-backend
	cd $(BACKEND_DIR) && uv run uvicorn app:app --host $(HOST) --port $(PORT) --reload

backend-prod: stop-backend
	cd $(BACKEND_DIR) && uv run uvicorn app:app --host $(HOST) --port $(PORT)

health:
	curl -s http://127.0.0.1:$(PORT)/

push-backend:
	cd $(BACKEND_DIR) && uv run python push-scripts.py $(BACKEND_PUSH_ARGS)

update-backend: push-backend

web-ui-build:
	cd $(WEB_UI_DIR) && npm ci && VITE_BASE_PATH=$(WEB_UI_BASE_PATH) npm run build

push-web-ui: web-ui-build
	cd $(BACKEND_DIR) && uv run python ../$(WEB_UI_DIR)/push-scripts.py $(WEB_UI_PUSH_ARGS)

update-web-ui: push-web-ui

push-all update-all update push:
	@case "$(COMPONENT)" in \
		all) \
			$(MAKE) push-backend PUSH_ARGS="$(PUSH_ARGS)" DEPLOY_HOST="$(DEPLOY_HOST)"; \
			$(MAKE) push-web-ui WEB_PUSH_ARGS="$(WEB_PUSH_ARGS)" DEPLOY_HOST="$(DEPLOY_HOST)"; \
			;; \
		backend) \
			$(MAKE) push-backend PUSH_ARGS="$(PUSH_ARGS)" DEPLOY_HOST="$(DEPLOY_HOST)"; \
			;; \
		web) \
			$(MAKE) push-web-ui WEB_PUSH_ARGS="$(WEB_PUSH_ARGS)" DEPLOY_HOST="$(DEPLOY_HOST)"; \
			;; \
		*) \
			echo "Invalid COMPONENT=$(COMPONENT). Use all, backend, or web."; \
			exit 1; \
			;; \
	esac
