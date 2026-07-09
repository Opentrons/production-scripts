.DEFAULT_GOAL := help

HOST ?= 0.0.0.0
PORT ?= 8090
COMPONENT ?= all
DEPLOY_HOST ?=
PUSH_ARGS ?=
WEB_PUSH_ARGS ?=

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
	@echo "  make high-voltage            Run high-voltage manual test workflow"
	@echo ""
	@echo "Variables:"
	@echo "  HOST=0.0.0.0 PORT=8090"
	@echo "  COMPONENT=all|backend|web DEPLOY_HOST=IP"
	@echo "  PUSH_ARGS='...' WEB_PUSH_ARGS='...'"
	@echo ""
	@echo "Subproject help:"
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
	$(MAKE) -C opentrons-productions web-ui-build

.PHONY: opentrons-update
opentrons-update:
	$(MAKE) -C opentrons-productions update \
		COMPONENT=$(COMPONENT) \
		DEPLOY_HOST=$(DEPLOY_HOST) \
		PUSH_ARGS="$(PUSH_ARGS)" \
		WEB_PUSH_ARGS="$(WEB_PUSH_ARGS)"

.PHONY: high-voltage
high-voltage:
	$(MAKE) -C tools/high_voltage_test run
