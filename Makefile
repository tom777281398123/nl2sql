.PHONY: help middleware nmiddleware up down restart logs clean build-volumes pull ps

PROJECT_DIR := $(shell pwd)
COMPOSE_PROJECT_NAME := storekeeper-nl2sql
DOCKER_COMPOSE := PROJECT_ROOT=$(PROJECT_DIR) docker compose \
	-p $(COMPOSE_PROJECT_NAME) \
	-f docker/docker-compose-debug.yml \
	--env-file docker/.env.debug \
	--profile middleware

help:
	@echo "Available commands:"
	@echo "  make middleware    - Start all middleware services"
	@echo "  make up            - Start all services"
	@echo "  make down          - Stop all services"
	@echo "  make restart       - Restart all services"
	@echo "  make logs          - View logs from all services"
	@echo "  make ps            - List middleware containers"
	@echo "  make clean         - Remove all containers and data"
	@echo "  make build-volumes - Create necessary volume directories"
	@echo "  make pull          - Pull latest Docker images"

middleware: build-volumes
	@echo "Starting NL2SQL middleware services..."
	$(DOCKER_COMPOSE) up -d --wait
	@echo ""
	@echo "✓ All NL2SQL middleware services are running!"
	@echo "=========================================="
	@echo "  MySQL:          localhost:3306"
	@echo "  Elasticsearch:  localhost:9200"
	@echo "  Kibana:         localhost:5601"
	@echo "  Qdrant HTTP:    localhost:6333"
	@echo "  Qdrant gRPC:    localhost:6334"
	@echo "  Embedding:      localhost:8081"
	@echo "=========================================="
	@echo ""
	@echo "Data volumes location: $(PROJECT_DIR)/docker/data/"
	@echo "Init scripts location: $(PROJECT_DIR)/scripts/"

nmiddleware: middleware

pull:
	@echo "Pulling latest Docker images..."
	$(DOCKER_COMPOSE) pull

up:
	@echo "Starting NL2SQL middleware services..."
	$(DOCKER_COMPOSE) up -d

down:
	@echo "Stopping NL2SQL middleware services..."
	$(DOCKER_COMPOSE) down

restart: down up
	@echo "✓ Services restarted"

logs:
	$(DOCKER_COMPOSE) logs -f

ps:
	$(DOCKER_COMPOSE) ps

# 保留embed的 数据
clean:
	@echo "Removing all containers, networks, and data..."
	$(DOCKER_COMPOSE) down -v
	rm -rf $(PROJECT_DIR)/docker/data/mysql
	rm -rf $(PROJECT_DIR)/docker/data/elasticsearch
	rm -rf $(PROJECT_DIR)/docker/data/qdrant
	@echo "✓ Cleaned up (embedding data preserved)"

build-volumes:
	@echo "Creating volume directories..."
	mkdir -p $(PROJECT_DIR)/docker/data/mysql
	mkdir -p $(PROJECT_DIR)/docker/data/elasticsearch
	mkdir -p $(PROJECT_DIR)/docker/data/qdrant
	mkdir -p $(PROJECT_DIR)/docker/data/embedding
	@echo "✓ Volume directories created"
