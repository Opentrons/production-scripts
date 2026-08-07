REPOSITORY_ROOT := ../..
APP_DIR := apps/hardwares
APP_NAME := productions-hardwares
ENTRYPOINT := $(APP_DIR)/src/cli/main.py
CONFIG_JSON := $(APP_DIR)/src/leveling_testing/leveling_config.json
CONFIG_DEST := leveling_testing
COMPENSATION_TEMPLATE := $(APP_DIR)/src/leveling_testing/Templete.xlsx

ifeq ($(OS),Windows_NT)
	ADD_DATA_SEP := ;
	EXE_PATH := $(REPOSITORY_ROOT)/dist/$(APP_NAME).exe
else
	ADD_DATA_SEP := :
	EXE_PATH := $(REPOSITORY_ROOT)/dist/$(APP_NAME)
endif

PYINSTALLER_ARGS := \
	--onefile \
	--name $(APP_NAME) \
	--hidden-import cli.__version__ \
	--hidden-import leveling_testing.config \
	--hidden-import leveling_testing.type \
	--hidden-import leveling_testing.model.base \
	--hidden-import leveling_testing.report.report \
	--hidden-import opentonrs_api.hardware_control.hardware_control \
	--hidden-import opentonrs_api.protocol.protocol_context \
	--hidden-import opentonrs_api.maintenance_api.maintenance_run \
	--add-data "$(CONFIG_JSON)$(ADD_DATA_SEP)$(CONFIG_DEST)" \
	$(ENTRYPOINT)

.DEFAULT_GOAL := run

.PHONY: run
run:
	cd $(REPOSITORY_ROOT) && uv run --package productions-hardwares productions-hardwares

.PHONY: leveling
leveling:
	cd $(REPOSITORY_ROOT) && uv run --package productions-hardwares productions-hardwares leveling

.PHONY: simulate
simulate:
	cd $(REPOSITORY_ROOT) && uv run --package productions-hardwares productions-hardwares leveling --simulate --test all --robot-sn SIM-MAKE --robot-ip simulator

.PHONY: sync
sync:
	cd $(REPOSITORY_ROOT) && uv sync --package productions-hardwares

.PHONY: sync-build
sync-build:
	cd $(REPOSITORY_ROOT) && uv sync --package productions-hardwares --group build

.PHONY: build
build: sync-build
	cd $(REPOSITORY_ROOT) && uv run --package productions-hardwares pyinstaller $(PYINSTALLER_ARGS)
	@echo "Built executable: $(EXE_PATH)"

.PHONY: update-compensation
update-compensation:
	@if [ ! -f "$(REPOSITORY_ROOT)/$(COMPENSATION_TEMPLATE)" ]; then \
		echo "Error: compensation template not found: $(COMPENSATION_TEMPLATE)"; \
		exit 1; \
	fi
	cd $(REPOSITORY_ROOT) && uv run --package productions-hardwares python -m leveling_testing.convert_compensations

.PHONY: test
test:
	cd $(REPOSITORY_ROOT) && uv run --package productions-hardwares pytest -q $(APP_DIR)/tests

.PHONY: clean
clean:
	cd $(REPOSITORY_ROOT) && uv run --package productions-hardwares python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['build', 'dist', '.pytest_cache']]; [p.unlink(missing_ok=True) for p in pathlib.Path('.').rglob('*.pyc')]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"

.PHONY: help
help:
	@echo "make run                  Start interactive hardware app"
	@echo "make leveling             Start leveling CLI"
	@echo "make simulate             Run all leveling tests in simulation mode"
	@echo "make build                Build current-platform executable"
	@echo "make update-compensation  Update leveling_config.json"
	@echo "make test                 Run hardware tests"
	@echo "make clean                Remove build artifacts"
