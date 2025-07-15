.PHONY: build-exe
build-exe:
	@echo "building exe"
	python -m __version__

.PHONY: build-ui
build-ui:
	@echo "building ui"
	@cd web_ui && npm run build
	@echo "Complete! target files -> ${PWD}/dist"

.PHONY: scp-web-ui
scp-web-ui:
	@echo "scp-web-ui..."
	ssh -t root@$(host) "sudo rm -rf /opt/web-ui/*"
	scp -r dist/* root@${host}:/opt/web-ui
	ssh -t root@$(host) "sudo systemctl restart nginx"

.PHONY: push-web-ui
host ?= 192.168.6.48
push-web-ui:
	@echo "push-web-ui"
	$(MAKE) build-ui
	$(MAKE) scp-web-ui
	@echo "Complete!"

.PHONY: push-data-center
host ?=192.168.6.48
push-data-center:
	@echo "push-data-center"
	@cd data_center && python upload_to_server.py --host $(host)

.PHONY: start-server-front
start-server-front:
	@echo "start front-end server"
	@echo "open web page on http://127.0.0.1:8000"
	@cd web_ui/ui && python -m http.server
	
