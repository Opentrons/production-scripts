.DEFAULT_GOAL := help

HOST ?= 0.0.0.0
API_PORT ?= 8090
DEPLOY_API_PORT ?= 18090
WEB_PORT ?= 8091
WEB_HTTP_PORT ?= 80
WEB_HTTPS_PORT ?= 443
DATA_CENTER_HTTP_PORT ?= 8090
DATA_CENTER_ALLOWED_CIDRS ?= 192.168.6.0/24,192.168.7.0/24,192.168.8.0/24
SERVER_NAME ?= _
SSL_CERTIFICATE ?=
SSL_CERTIFICATE_KEY ?=
REMOTE_HOST ?= 192.168.6.55
REMOTE_USER ?= root
REMOTE_SSH_PORT ?= 22
REMOTE_ROOT ?= /opt/production-platform
REMOTE_UV_BIN ?= /root/.local/bin/uv
REMOTE_SSL_CERTIFICATE ?= /etc/ssl/production-platform/production-platform.crt
REMOTE_SSL_CERTIFICATE_KEY ?= /etc/ssl/production-platform/production-platform.key
DURO_API_KEY_PATH ?= $(CURDIR)/apps/backend/auth-files/duro-api-key.txt
REMOTE_DURO_API_KEY_PATH ?= /configs/duro-api-key.txt

.PHONY: help sync dev dev-stop-ports backend-dev backend-prod backend-test backend-health web-install web-dev web-build hardware hardware-test hardware-build high-voltage test build deploy-backend deploy-web deploy-remote

help:
	@echo "Production Scripts targets:"
	@echo "  make sync             Install both Python applications"
	@echo "  make dev              Restart occupied dev ports and start backend + web"
	@echo "  make backend-dev      Start FastAPI with reload"
	@echo "  make backend-prod     Start FastAPI"
	@echo "  make backend-test     Run backend tests"
	@echo "  make backend-health   Check the backend root endpoint"
	@echo "  make web-install      Install web dependencies"
	@echo "  make web-dev          Start the Vue application"
	@echo "  make web-build        Build the Vue application"
	@echo "  make hardware         Start the hardware application"
	@echo "  make hardware-test    Run hardware tests"
	@echo "  make hardware-build   Build the hardware executable"
	@echo "  make high-voltage     Run the high-voltage tool"
	@echo "  make test             Run backend and hardware tests"
	@echo "  make build            Build web and hardware executable"
	@echo "  make deploy-backend   Install/restart the backend service"
	@echo "  make deploy-web       Build/configure the nginx site"
	@echo "  make deploy-remote    Build and deploy web/backend to $(REMOTE_HOST)"

sync:
	uv sync --all-packages

dev-stop-ports:
	@command -v lsof >/dev/null 2>&1 || { echo "Error: lsof is required to free dev ports"; exit 1; }
	@for port in $(API_PORT) $(WEB_PORT); do \
		pids=$$(lsof -tiTCP:$$port -sTCP:LISTEN 2>/dev/null | sort -u); \
		if [ -n "$$pids" ]; then \
			echo "Stopping process(es) listening on port $$port: $$(echo $$pids | tr '\n' ' ')"; \
			kill -TERM $$pids 2>/dev/null || true; \
			sleep 1; \
			remaining=$$(lsof -tiTCP:$$port -sTCP:LISTEN 2>/dev/null | sort -u); \
			if [ -n "$$remaining" ]; then \
				echo "Force stopping process(es) still listening on port $$port: $$(echo $$remaining | tr '\n' ' ')"; \
				kill -KILL $$remaining 2>/dev/null || true; \
			fi; \
		fi; \
	done

dev: dev-stop-ports
	$(MAKE) -j2 backend-dev web-dev

backend-dev:
	uv run --package production-backend uvicorn app:app --host $(HOST) --port $(API_PORT) --reload --reload-dir apps/backend/src

backend-prod:
	uv run --package production-backend uvicorn app:app --host $(HOST) --port $(API_PORT)

backend-test:
	uv run --package production-backend pytest -q apps/backend/tests

backend-health:
	curl -fsS http://127.0.0.1:$(API_PORT)/

web-install:
	cd apps/web-ui && npm ci

web-dev:
	cd apps/web-ui && npm run dev -- --host $(HOST) --port $(WEB_PORT)

web-build:
	cd apps/web-ui && npm run build

hardware:
	$(MAKE) -C apps/hardwares run

hardware-test:
	$(MAKE) -C apps/hardwares test

hardware-build:
	$(MAKE) -C apps/hardwares build

high-voltage:
	uv run --package productions-hardwares python -m tools.high_voltage_test.main

test: backend-test hardware-test

build: web-build hardware-build

deploy-backend:
	sudo API_PORT=$(API_PORT) bash deploy/backend.sh

deploy-web:
	sudo API_PORT=$(API_PORT) WEB_HTTP_PORT=$(WEB_HTTP_PORT) WEB_HTTPS_PORT=$(WEB_HTTPS_PORT) SERVER_NAME=$(SERVER_NAME) SSL_CERTIFICATE=$(SSL_CERTIFICATE) SSL_CERTIFICATE_KEY=$(SSL_CERTIFICATE_KEY) bash deploy/web.sh

deploy-remote: web-build
	REMOTE_HOST="$(REMOTE_HOST)" \
	REMOTE_USER="$(REMOTE_USER)" \
	REMOTE_SSH_PORT="$(REMOTE_SSH_PORT)" \
	REMOTE_ROOT="$(REMOTE_ROOT)" \
	REMOTE_UV_BIN="$(REMOTE_UV_BIN)" \
	API_PORT="$(DEPLOY_API_PORT)" \
	WEB_HTTP_PORT="$(WEB_HTTP_PORT)" \
	WEB_HTTPS_PORT="$(WEB_HTTPS_PORT)" \
	DATA_CENTER_HTTP_PORT="$(DATA_CENTER_HTTP_PORT)" \
	DATA_CENTER_ALLOWED_CIDRS="$(DATA_CENTER_ALLOWED_CIDRS)" \
	SERVER_NAME="$(SERVER_NAME)" \
	SSL_CERTIFICATE="$(REMOTE_SSL_CERTIFICATE)" \
	SSL_CERTIFICATE_KEY="$(REMOTE_SSL_CERTIFICATE_KEY)" \
	DURO_API_KEY_PATH="$(DURO_API_KEY_PATH)" \
	REMOTE_DURO_API_KEY_PATH="$(REMOTE_DURO_API_KEY_PATH)" \
	bash deploy/remote.sh
