.PHONY: build-exe
install:
	@echo "building"
	pyinstaller -F --ico="assets/logo.ico" --name=Productions production_scripts.py