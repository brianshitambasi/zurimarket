.PHONY: help dev up down logs clean

help:
	@echo "Available commands:"
	@echo "  make dev      - Start development environment"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make logs     - Show logs"
	@echo "  make clean    - Clean up containers and volumes"

dev:
	docker-compose -f docker-compose.dev.yml up -d
	sleep 5
	cd backend/services/auth-service && uvicorn app.main:app --reload --port 8000 &
	cd backend/services/product-service && uvicorn app.main:app --reload --port 8001 &
	@echo "Services started:"
	@echo "  Auth Service: http://localhost:8000/docs"
	@echo "  Product Service: http://localhost:8001/docs"

up:
	docker-compose -f docker-compose.dev.yml up -d

down:
	docker-compose -f docker-compose.dev.yml down

logs:
	docker-compose -f docker-compose.dev.yml logs -f

clean:
	docker-compose -f docker-compose.dev.yml down -v
