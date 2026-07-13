.DEFAULT_GOAL := help

HOST ?= 0.0.0.0
PORT ?= 5173

NODE_MODULES_STAMP := node_modules/.package-lock.json

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  make init     Install frontend dependencies with npm ci"
	@echo "  make dev      Start the Vite dev server"
	@echo "  make start    Alias of dev"
	@echo "  make build    Build the static frontend"
	@echo "  make preview  Build and preview the static frontend"
	@echo "  make clean    Remove local frontend artifacts"
	@echo ""
	@echo "Variables:"
	@echo "  HOST=0.0.0.0 PORT=5173"

$(NODE_MODULES_STAMP): package.json package-lock.json
	npm ci

.PHONY: init
init: $(NODE_MODULES_STAMP)
	@echo "productions-index dependencies ready"

.PHONY: dev start
dev start: init
	npm run dev -- --host $(HOST) --port $(PORT)

.PHONY: build
build: init
	npm run build

.PHONY: preview
preview: build
	npm run preview -- --host $(HOST) --port $(PORT)

.PHONY: clean
clean:
	rm -rf dist node_modules
