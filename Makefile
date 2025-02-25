###############################################################################
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
###############################################################################

ENV ?= default

DOCKER_COMPOSE_ARGS=--project-name wis2-gb --file docker-compose-${ENV}.yml --file docker-compose-${ENV}.override.yml

echo:
	@echo ${ENV}
	@echo ${DOCKER_COMPOSE_ARGS}

build: echo
	docker-compose $(DOCKER_COMPOSE_ARGS) build

up:
	docker-compose $(DOCKER_COMPOSE_ARGS) up --detach

down:
	docker-compose $(DOCKER_COMPOSE_ARGS) down

start:
	docker-compose $(DOCKER_COMPOSE_ARGS) start

stop:
	docker-compose $(DOCKER_COMPOSE_ARGS) stop

restart: down up

force-build:
	docker-compose $(DOCKER_COMPOSE_ARGS) build --no-cache

logs:
	docker-compose $(DOCKER_COMPOSE_ARGS) logs --follow

clean:
	docker system prune -f
	docker volume prune -f

rm:
	docker volume rm $(shell docker volume ls --filter name=wis2-gb -q)

.PHONY: build up down start stop restart force-build logs rm clean
