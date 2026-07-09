PROJECT_ROOT := $(abspath ../..)
PYTHON := uv run python

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
	cd $(PROJECT_ROOT) && uv sync

pip:
	cd $(PROJECT_ROOT) && uv pip list

run: setup
	cd $(PROJECT_ROOT) && $(PYTHON) -m tools.high_voltage_test.main

gpt: setup
	cd $(PROJECT_ROOT) && $(PYTHON) -m tools.high_voltage_test.GPT.GptDevice

show:
	@echo $(PROJECT_ROOT)
	@echo $(PYTHON)
