.DEFAULT_GOAL := help

HOST ?= 0.0.0.0
PORT ?= 8090
INDEX_PORT ?= 5173
INDEX_DEPLOY_PORT ?= 80
INDEX_REMOTE_DIR ?= /opt/data-handler/index-productions
OPENTRONS_WEB_PORT ?= 8091
OPENTRONS_API_PORT ?= 8090
OPENTRONS_WEB_BASE_PATH ?= /opentrons-productions/
OPENTRONS_PROXY_PATH ?= /opentrons-productions
OPENTRONS_LEGACY_PROXY_PATH ?= /opetrons-productions
WEB_UI_BASE_PATH ?= /
COMPONENT ?= all
DEPLOY_HOST ?=
PUSH_ARGS ?=
WEB_PUSH_ARGS ?=
INDEX_PUSH_ARGS ?=

INDEX_DEPLOY_ARGS := $(INDEX_PUSH_ARGS)
ifneq ($(DEPLOY_HOST),)
INDEX_DEPLOY_ARGS += --host $(DEPLOY_HOST)
endif
INDEX_DEPLOY_ARGS += --remote-dir $(INDEX_REMOTE_DIR)
INDEX_DEPLOY_ARGS += --site-port $(INDEX_DEPLOY_PORT)
INDEX_DEPLOY_ARGS += --opentrons-port $(OPENTRONS_WEB_PORT)
INDEX_DEPLOY_ARGS += --opentrons-api-port $(OPENTRONS_API_PORT)
INDEX_DEPLOY_ARGS += --opentrons-path $(OPENTRONS_PROXY_PATH)
INDEX_DEPLOY_ARGS += --legacy-opentrons-path $(OPENTRONS_LEGACY_PROXY_PATH)

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  make help                    Show this help message"
	@echo "  make test-cli                Start interactive test-cli"
	@echo "  make leveling                Start leveling CLI"
	@echo "  make simulate                Run all leveling tests in simulation mode"
	@echo "  make test-cli-build          Build test-cli executable"
	@echo "  make build-exe               Alias of test-cli-build"
	@echo "  make update-compensation     Update leveling_config.json from Templete.xlsx"
	@echo "  make opentrons-install       Install opentrons-productions backend dependencies"
	@echo "  make opentrons-backend       Start opentrons-productions backend with reload"
	@echo "  make opentrons-backend-prod  Start opentrons-productions backend without reload"
	@echo "  make opentrons-health        Check opentrons-productions backend health"
	@echo "  make opentrons-web-ui-build  Build opentrons-productions web UI"
	@echo "  make opentrons-update        Update opentrons-productions remote code"
	@echo "  make deploy-opentrons-productions Deploy opentrons-productions for indexed routing"
	@echo "  make index-productions-init  Install productions index dependencies"
	@echo "  make index-productions-dev   Start the productions index page"
	@echo "  make index-productions-build Build the productions index page"
	@echo "  make deploy-index-productions Deploy productions index and nginx proxy"
	@echo "  make deploy-productions      Deploy opentrons-productions and productions index"
	@echo "  make high-voltage            Run high-voltage manual test workflow"
	@echo ""
	@echo "Variables:"
	@echo "  HOST=0.0.0.0 PORT=8090 INDEX_PORT=5173 INDEX_DEPLOY_PORT=80"
	@echo "  COMPONENT=all|backend|web DEPLOY_HOST=IP"
	@echo "  PUSH_ARGS='...' WEB_PUSH_ARGS='...' INDEX_PUSH_ARGS='...'"
	@echo "  OPENTRONS_WEB_BASE_PATH=/opentrons-productions/"
	@echo "  OPENTRONS_PROXY_PATH=/opentrons-productions OPENTRONS_WEB_PORT=8091 OPENTRONS_API_PORT=8090"
	@echo ""
	@echo "Subproject help:"
	@echo "  make -C index-productions help"
	@echo "  make -C test_cli help"
	@echo "  make -C opentrons-productions help"
	@echo "  make -C tools/high_voltage_test help"

.PHONY: test-cli
test-cli:
	$(MAKE) -C test_cli run

.PHONY: leveling
leveling:
	$(MAKE) -C test_cli leveling

.PHONY: simulate
simulate:
	$(MAKE) -C test_cli simulate

.PHONY: test-cli-build build-exe
test-cli-build build-exe:
	$(MAKE) -C test_cli build

.PHONY: update-compensation
update-compensation:
	$(MAKE) -C test_cli update-compensation

.PHONY: opentrons-install
opentrons-install:
	$(MAKE) -C opentrons-productions install

.PHONY: opentrons-backend
opentrons-backend:
	$(MAKE) -C opentrons-productions backend HOST=$(HOST) PORT=$(PORT)

.PHONY: opentrons-backend-prod
opentrons-backend-prod:
	$(MAKE) -C opentrons-productions backend-prod HOST=$(HOST) PORT=$(PORT)

.PHONY: opentrons-health
opentrons-health:
	$(MAKE) -C opentrons-productions health PORT=$(PORT)

.PHONY: opentrons-web-ui-build
opentrons-web-ui-build:
	$(MAKE) -C opentrons-productions web-ui-build WEB_UI_BASE_PATH=$(WEB_UI_BASE_PATH)

.PHONY: opentrons-update
opentrons-update:
	$(MAKE) -C opentrons-productions update \
		COMPONENT=$(COMPONENT) \
		DEPLOY_HOST=$(DEPLOY_HOST) \
		PUSH_ARGS="$(PUSH_ARGS)" \
		WEB_PUSH_ARGS="$(WEB_PUSH_ARGS)" \
		WEB_UI_BASE_PATH=$(WEB_UI_BASE_PATH)

.PHONY: deploy-opentrons-productions
deploy-opentrons-productions:
	$(MAKE) -C opentrons-productions update \
		COMPONENT=$(COMPONENT) \
		DEPLOY_HOST=$(DEPLOY_HOST) \
		PUSH_ARGS="$(PUSH_ARGS)" \
		WEB_PUSH_ARGS="$(WEB_PUSH_ARGS)" \
		WEB_UI_BASE_PATH=$(OPENTRONS_WEB_BASE_PATH)

.PHONY: index-productions-init
index-productions-init:
	$(MAKE) -C index-productions init

.PHONY: index-productions-dev
index-productions-dev:
	$(MAKE) -C index-productions dev HOST=$(HOST) PORT=$(INDEX_PORT)

.PHONY: index-productions-build
index-productions-build:
	$(MAKE) -C index-productions build

.PHONY: deploy-index-productions
deploy-index-productions: index-productions-build
	uv run python deploy-index-productions.py $(INDEX_DEPLOY_ARGS)

.PHONY: deploy-productions
deploy-productions:
	$(MAKE) deploy-opentrons-productions \
		COMPONENT=$(COMPONENT) \
		DEPLOY_HOST=$(DEPLOY_HOST) \
		PUSH_ARGS="$(PUSH_ARGS)" \
		WEB_PUSH_ARGS="$(WEB_PUSH_ARGS)" \
		OPENTRONS_WEB_BASE_PATH=$(OPENTRONS_WEB_BASE_PATH)
	$(MAKE) deploy-index-productions \
		DEPLOY_HOST=$(DEPLOY_HOST) \
		INDEX_PUSH_ARGS="$(INDEX_PUSH_ARGS)" \
		INDEX_REMOTE_DIR=$(INDEX_REMOTE_DIR) \
		INDEX_DEPLOY_PORT=$(INDEX_DEPLOY_PORT) \
		OPENTRONS_WEB_PORT=$(OPENTRONS_WEB_PORT) \
		OPENTRONS_API_PORT=$(OPENTRONS_API_PORT) \
		OPENTRONS_PROXY_PATH=$(OPENTRONS_PROXY_PATH) \
		OPENTRONS_LEGACY_PROXY_PATH=$(OPENTRONS_LEGACY_PROXY_PATH)

.PHONY: high-voltage
high-voltage:
	$(MAKE) -C tools/high_voltage_test run
