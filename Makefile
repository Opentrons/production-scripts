.DEFAULT_GOAL := help

HOST ?= 0.0.0.0
PORT ?= 8090
PRODUCTIONS_INDEX_PORT ?= 5173
PRODUCTIONS_INDEX_DEPLOY_PORT ?= 80
PRODUCTIONS_INDEX_REMOTE_DIR ?= /opt/data-handler/productions-index
PRODUCTIONS_OPENTRONS_WEB_PORT ?= 8091
PRODUCTIONS_OPENTRONS_API_PORT ?= 8090
PRODUCTIONS_OPENTRONS_WEB_BASE_PATH ?= /productions-opentrons/
PRODUCTIONS_OPENTRONS_PROXY_PATH ?= /productions-opentrons
PRODUCTIONS_OPENTRONS_LEGACY_PROXY_PATH ?= /opentrons-productions
PRODUCTIONS_OPENTRONS_TYPO_PROXY_PATH ?= /opetrons-productions
WEB_UI_BASE_PATH ?= /
COMPONENT ?= all
DEPLOY_HOST ?=
PUSH_ARGS ?=
WEB_PUSH_ARGS ?=
PRODUCTIONS_INDEX_PUSH_ARGS ?=

PRODUCTIONS_INDEX_DEPLOY_ARGS := $(PRODUCTIONS_INDEX_PUSH_ARGS)
ifneq ($(DEPLOY_HOST),)
PRODUCTIONS_INDEX_DEPLOY_ARGS += --host $(DEPLOY_HOST)
endif
PRODUCTIONS_INDEX_DEPLOY_ARGS += --remote-dir $(PRODUCTIONS_INDEX_REMOTE_DIR)
PRODUCTIONS_INDEX_DEPLOY_ARGS += --site-port $(PRODUCTIONS_INDEX_DEPLOY_PORT)
PRODUCTIONS_INDEX_DEPLOY_ARGS += --opentrons-port $(PRODUCTIONS_OPENTRONS_WEB_PORT)
PRODUCTIONS_INDEX_DEPLOY_ARGS += --opentrons-api-port $(PRODUCTIONS_OPENTRONS_API_PORT)
PRODUCTIONS_INDEX_DEPLOY_ARGS += --opentrons-path $(PRODUCTIONS_OPENTRONS_PROXY_PATH)
PRODUCTIONS_INDEX_DEPLOY_ARGS += --legacy-opentrons-path $(PRODUCTIONS_OPENTRONS_LEGACY_PROXY_PATH)
PRODUCTIONS_INDEX_DEPLOY_ARGS += --legacy-typo-opentrons-path $(PRODUCTIONS_OPENTRONS_TYPO_PROXY_PATH)

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
	@echo "  make productions-opentrons-install       Install productions-opentrons backend dependencies"
	@echo "  make productions-opentrons-backend       Start productions-opentrons backend with reload"
	@echo "  make productions-opentrons-backend-prod  Start productions-opentrons backend without reload"
	@echo "  make productions-opentrons-health        Check productions-opentrons backend health"
	@echo "  make productions-opentrons-web-ui-build  Build productions-opentrons web UI"
	@echo "  make productions-opentrons-update        Update productions-opentrons remote code"
	@echo "  make deploy-productions-opentrons Deploy productions-opentrons for indexed routing"
	@echo "  make productions-index-init  Install productions index dependencies"
	@echo "  make productions-index-dev   Start the productions index page"
	@echo "  make productions-index-build Build the productions index page"
	@echo "  make deploy-productions-index Deploy productions index and nginx proxy"
	@echo "  make deploy-productions      Deploy productions-opentrons and productions index"
	@echo "  make high-voltage            Run high-voltage manual test workflow"
	@echo ""
	@echo "Variables:"
	@echo "  HOST=0.0.0.0 PORT=8090 PRODUCTIONS_INDEX_PORT=5173 PRODUCTIONS_INDEX_DEPLOY_PORT=80"
	@echo "  COMPONENT=all|backend|web DEPLOY_HOST=IP"
	@echo "  PUSH_ARGS='...' WEB_PUSH_ARGS='...' PRODUCTIONS_INDEX_PUSH_ARGS='...'"
	@echo "  PRODUCTIONS_OPENTRONS_WEB_BASE_PATH=/productions-opentrons/"
	@echo "  PRODUCTIONS_OPENTRONS_PROXY_PATH=/productions-opentrons PRODUCTIONS_OPENTRONS_WEB_PORT=8091 PRODUCTIONS_OPENTRONS_API_PORT=8090"
	@echo ""
	@echo "Subproject help:"
	@echo "  make -C productions-index help"
	@echo "  make -C test_cli help"
	@echo "  make -C productions-opentrons help"
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

.PHONY: productions-opentrons-install
productions-opentrons-install:
	$(MAKE) -C productions-opentrons install

.PHONY: productions-opentrons-backend
productions-opentrons-backend:
	$(MAKE) -C productions-opentrons backend HOST=$(HOST) PORT=$(PORT)

.PHONY: productions-opentrons-backend-prod
productions-opentrons-backend-prod:
	$(MAKE) -C productions-opentrons backend-prod HOST=$(HOST) PORT=$(PORT)

.PHONY: productions-opentrons-health
productions-opentrons-health:
	$(MAKE) -C productions-opentrons health PORT=$(PORT)

.PHONY: productions-opentrons-web-ui-build
productions-opentrons-web-ui-build:
	$(MAKE) -C productions-opentrons web-ui-build WEB_UI_BASE_PATH=$(WEB_UI_BASE_PATH)

.PHONY: productions-opentrons-update
productions-opentrons-update:
	$(MAKE) -C productions-opentrons update \
		COMPONENT=$(COMPONENT) \
		DEPLOY_HOST=$(DEPLOY_HOST) \
		PUSH_ARGS="$(PUSH_ARGS)" \
		WEB_PUSH_ARGS="$(WEB_PUSH_ARGS)" \
		WEB_UI_BASE_PATH=$(WEB_UI_BASE_PATH)

.PHONY: deploy-productions-opentrons
deploy-productions-opentrons:
	$(MAKE) -C productions-opentrons update \
		COMPONENT=$(COMPONENT) \
		DEPLOY_HOST=$(DEPLOY_HOST) \
		PUSH_ARGS="$(PUSH_ARGS)" \
		WEB_PUSH_ARGS="$(WEB_PUSH_ARGS)" \
		WEB_UI_BASE_PATH=$(PRODUCTIONS_OPENTRONS_WEB_BASE_PATH)

.PHONY: productions-index-init
productions-index-init:
	$(MAKE) -C productions-index init

.PHONY: productions-index-dev
productions-index-dev:
	$(MAKE) -C productions-index dev HOST=$(HOST) PORT=$(PRODUCTIONS_INDEX_PORT)

.PHONY: productions-index-build
productions-index-build:
	$(MAKE) -C productions-index build

.PHONY: deploy-productions-index
deploy-productions-index: productions-index-build
	uv run python deploy-productions-index.py $(PRODUCTIONS_INDEX_DEPLOY_ARGS)

.PHONY: deploy-productions
deploy-productions:
	$(MAKE) deploy-productions-opentrons \
		COMPONENT=$(COMPONENT) \
		DEPLOY_HOST=$(DEPLOY_HOST) \
		PUSH_ARGS="$(PUSH_ARGS)" \
		WEB_PUSH_ARGS="$(WEB_PUSH_ARGS)" \
		PRODUCTIONS_OPENTRONS_WEB_BASE_PATH=$(PRODUCTIONS_OPENTRONS_WEB_BASE_PATH)
	$(MAKE) deploy-productions-index \
		DEPLOY_HOST=$(DEPLOY_HOST) \
		PRODUCTIONS_INDEX_PUSH_ARGS="$(PRODUCTIONS_INDEX_PUSH_ARGS)" \
		PRODUCTIONS_INDEX_REMOTE_DIR=$(PRODUCTIONS_INDEX_REMOTE_DIR) \
		PRODUCTIONS_INDEX_DEPLOY_PORT=$(PRODUCTIONS_INDEX_DEPLOY_PORT) \
		PRODUCTIONS_OPENTRONS_WEB_PORT=$(PRODUCTIONS_OPENTRONS_WEB_PORT) \
		PRODUCTIONS_OPENTRONS_API_PORT=$(PRODUCTIONS_OPENTRONS_API_PORT) \
		PRODUCTIONS_OPENTRONS_PROXY_PATH=$(PRODUCTIONS_OPENTRONS_PROXY_PATH) \
		PRODUCTIONS_OPENTRONS_LEGACY_PROXY_PATH=$(PRODUCTIONS_OPENTRONS_LEGACY_PROXY_PATH) \
		PRODUCTIONS_OPENTRONS_TYPO_PROXY_PATH=$(PRODUCTIONS_OPENTRONS_TYPO_PROXY_PATH)

.PHONY: high-voltage
high-voltage:
	$(MAKE) -C tools/high_voltage_test run
