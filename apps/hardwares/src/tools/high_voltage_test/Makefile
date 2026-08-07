WORKSPACE_ROOT := $(abspath ../../../../../..)
PYTHON := uv run --package productions-hardwares python

.DEFAULT_GOAL := help

.PHONY: help setup pip run gpt show

help:
	@echo "Available targets:"
	@echo "  make setup  Install root project dependencies with uv"
	@echo "  make pip    List packages in the uv environment"
	@echo "  make run    Run the high-voltage manual test workflow"
	@echo "  make gpt    Run the GPT device driver module"
	@echo "  make show   Show resolved project root and Python command"

setup:
	cd $(WORKSPACE_ROOT) && uv sync

pip:
	cd $(WORKSPACE_ROOT) && uv pip list

run: setup
	cd $(WORKSPACE_ROOT) && $(PYTHON) -m tools.high_voltage_test.main

gpt: setup
	cd $(WORKSPACE_ROOT) && $(PYTHON) -m tools.high_voltage_test.GPT.GptDevice

show:
	@echo $(WORKSPACE_ROOT)
	@echo $(PYTHON)
