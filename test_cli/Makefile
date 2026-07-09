PROJECT_ROOT := ..
APP_NAME := test-cli
ENTRYPOINT := test_cli/main.py
CONFIG_JSON := test_cli/leveling_test/leveling_config.json
CONFIG_DEST := test_cli/leveling_test
COMPENSATION_TEMPLATE := test_cli/leveling_test/Templete.xlsx

ifeq ($(OS),Windows_NT)
	ADD_DATA_SEP := ;
	EXE_PATH := $(PROJECT_ROOT)/dist/$(APP_NAME).exe
else
	ADD_DATA_SEP := :
	EXE_PATH := $(PROJECT_ROOT)/dist/$(APP_NAME)
endif

PYINSTALLER_ARGS := \
	--onefile \
	--name $(APP_NAME) \
	--hidden-import test_cli.__version__ \
	--hidden-import test_cli.leveling_test.config \
	--hidden-import test_cli.leveling_test.type \
	--hidden-import test_cli.leveling_test.model.base \
	--hidden-import test_cli.leveling_test.report.report \
	--hidden-import test_cli.core.hardware_control.hardware_control \
	--hidden-import test_cli.core.protocol.protocol_context \
	--hidden-import test_cli.core.maintenance_api.maintenance_run \
	--hidden-import tools.inquirer \
	--hidden-import tools.reading_laser \
	--add-data "$(CONFIG_JSON)$(ADD_DATA_SEP)$(CONFIG_DEST)" \
	$(ENTRYPOINT)

.DEFAULT_GOAL := run

.PHONY: run
run:
	cd $(PROJECT_ROOT) && uv run $(APP_NAME)

.PHONY: leveling
leveling:
	cd $(PROJECT_ROOT) && uv run $(APP_NAME) leveling

.PHONY: simulate
simulate:
	cd $(PROJECT_ROOT) && uv run $(APP_NAME) leveling --simulate --test all --robot-sn SIM-MAKE --robot-ip simulator

.PHONY: sync
sync:
	cd $(PROJECT_ROOT) && uv sync

.PHONY: sync-build
sync-build:
	cd $(PROJECT_ROOT) && uv sync --group build

.PHONY: build
build: sync-build
	cd $(PROJECT_ROOT) && uv run pyinstaller $(PYINSTALLER_ARGS)
	@echo "Built executable: $(EXE_PATH)"

.PHONY: build-clean
build-clean: clean build

.PHONY: update-compensation
update-compensation:
	@if [ ! -f "$(PROJECT_ROOT)/$(COMPENSATION_TEMPLATE)" ]; then \
		echo "Error: compensation template not found: $(COMPENSATION_TEMPLATE)"; \
		echo "Please put Templete.xlsx under test_cli/leveling_test/ and retry."; \
		exit 1; \
	fi
	cd $(PROJECT_ROOT) && uv run python -m test_cli.leveling_test.convert_compensations

.PHONY: test
test:
	cd $(PROJECT_ROOT) && uv run pytest -v

.PHONY: clean
clean:
	cd $(PROJECT_ROOT) && uv run python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['build', 'dist', 'test_cli.egg-info', '.pytest_cache']]; [p.unlink(missing_ok=True) for p in pathlib.Path('.').rglob('*.pyc')]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"

.PHONY: help
help:
	@echo "make                 Start interactive test-cli"
	@echo "make leveling        Start leveling CLI"
	@echo "make simulate        Run all leveling tests in simulation mode"
	@echo "make build           Build current-platform executable into ../dist"
	@echo "make build-clean     Clean then build executable"
	@echo "make update-compensation  Update leveling_config.json from test_cli/leveling_test/Templete.xlsx"
	@echo "make clean           Remove build artifacts"
