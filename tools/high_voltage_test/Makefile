PROJECT_ROOT := $(abspath ../..)
PYTHON := uv run python

.PHONY: setup pip run gpt show

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
