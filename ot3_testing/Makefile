# ============================================
# Leveling Test Commands
# ============================================

.PHONY: run-leveling-test
run-leveling-test:
	@echo "Running leveling_test.__main__..."
	cd .. && python -m ot3_testing.leveling_test.__main__

.PHONY: run-main
run-main:
	@echo "Running main.py..."
	cd .. && python -m ot3_testing.main

.PHONY: update-compensation
update-compensation:
	@echo "Updating compensation data from Templete.xlsx..."
	cd leveling_test && python convert_compensations.py

# ============================================
# Packaging Commands
# ============================================

.PHONY: build-mac
build-mac:
	@echo "Building executable for macOS with PyInstaller..."
	python package.spec

.PHONY: build-win
build-win:
	@echo "Building executable for Windows with PyInstaller..."
	python package-win.spec

.PHONY: install-package
install-package:
	@echo "Installing package in development mode..."
	pip install -e .

.PHONY: build-wheel
build-wheel:
	@echo "Building wheel package..."
	python setup.py bdist_wheel

.PHONY: clean-build
clean-build:
	@echo "Cleaning build artifacts..."
	rm -rf build/ dist/ __pycache__/ *.egg-info/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete

.PHONY: package
package: clean-build build-wheel
	@echo "Package build complete. Wheel file is in dist/"

# ============================================
# Development Commands
# ============================================

.PHONY: install-deps
install-deps:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

.PHONY: test
test:
	@echo "Running tests..."
	python -m pytest tests/ -v
