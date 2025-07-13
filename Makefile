# Define variables
UID := $(shell id -u)
GID := $(shell id -g)

.PHONY: build up down logs ps shell clean restart

# Export UID/GID for docker-compose
export UID
export GID

# Build all containers
build:
	@echo "Building containers with UID=$(UID) and GID=$(GID)"
	docker compose build

# Start all containers in detached mode
up:
	@echo "Starting containers with UID=$(UID) and GID=$(GID)"
	docker compose up -d

# Stop all containers
down:
	docker compose down

# Show logs from all containers
logs:
	docker compose logs -f

# Show status of containers
ps:
	docker compose ps

# Access shell in a specific container (usage: make shell SERVICE=main)
shell:
	@[ "$(SERVICE)" ] || ( echo "ERROR: Service not specified. Usage: make shell SERVICE=main"; exit 1 )
	docker compose exec $(SERVICE) /bin/bash

# Clean volumes (use with caution)
clean:
	docker compose down -v

# Restart services (usage: make restart SERVICE=main or make restart for all)
restart:
ifdef SERVICE
	docker compose restart $(SERVICE)
else
	docker compose restart
endif

# All-in-one target to build and start
all: build up

# Default target
.DEFAULT_GOAL := all
