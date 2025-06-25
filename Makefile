# Makefile for Lookyloo Service

.PHONY: start run_once stop

start:
	docker build -t assemblyline-service-lookyloo . && \
	docker run --name al_svc_lookyloo -p 5100:5100 assemblyline-service-lookyloo

run_once:
	docker exec -it al_svc_lookyloo python -m assemblyline_v4_service.dev.run_service_once lookyloo.lookyloo.LookyLoo test.yml && \
	docker exec -it al_svc_lookyloo cat test.yml_lookyloo/result.json

stop:
	docker stop al_svc_lookyloo && docker rm al_svc_lookyloo

enter:
	docker exec -it al_svc_lookyloo /bin/bash
