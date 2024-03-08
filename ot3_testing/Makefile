.PHONY: install
install:
	@echo "install"
	npm install

.PHONY: push-ot3-testing-server
push-ot3-testing-step1:
	@echo "pushing"
	scp -r -i "devices/rsa_install/id_rsa" !(vue-ui) ./ root@192.168.6.196:/opt/ot3-testing-server

.PHONY: push-ot3-testing-ui
push-ot3-testing-step2:
	@echo "pushing"
	scp -r -i "devices/rsa_install/id_rsa" ./vue-ui/ot3_testing_ui/dist root@192.168.6.196:/opt/ot3-testing-server/

.PHONY: clean-ot3-testing
clean-ot3-testing:
	@echo "clean server"
	ssh -i "devices/rsa_install/id_rsa" root@192.168.6.196 rm -rf /opt/ot3-testing-server/*

.PHONY: sync-ot3-testing
sync-ot3-testing:
	@echo "sync-ot3-testing"
	make clean-ot3-testing
	make push-ot3-testing

.PHONY: reload-server
reload-server:
	ssh -i "devices/rsa_install/id_rsa" root@192.168.6.196 cd /opt/ot3-testing-server/ && python -m gunicorn -b 0.0.0.0:8080 -w 4 server.start_server:app -k uvicorn.workers.UvicornWorker -D


.PHONY: build-vue-ui
build-vue-ui:
	cd vue-ui/ot3_testing_ui
	npm run build


