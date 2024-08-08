.PHONY: build-exe
build-exe:
	@echo "building exe"
	python -m __version__

.PHONY: build-ui
build-ui:
	@echo "building ui"
	@cd web_ui && npm run build
	@echo "Complete! target files -> ${PWD}/dist"

.PHONY: start-server-back
start-server-back:
	@echo "start back-end server"
	python -m server.start_server

.PHONY: start-server-front
start-server-front:
	@echo "start front-end server"
	@echo "open web page on http://127.0.0.1:8000"
	@cd web_ui/ui && python -m http.server
	
