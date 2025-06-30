IMAGE_NAME := floodcast-app

.PHONY: build run clean fclean localenv prodenv

localenv:
	@echo "Creating .env for local development..."
	@echo "MONGO_URI=\"mongodb://host.docker.internal:27017\"" > .env
	@echo ".env created with local MONGO_URI."

prodenv:
	@echo "Creating .env for production environment..." && \
	if [ -z "$$MONGO_URI" ]; then \
		echo "Error: MONGO_URI environment variable is not set. Please set it before running 'make prodenv'."; \
		exit 1; \
	fi && \
	echo "MONGO_URI=\"$$MONGO_URI\"" > .env && \
	echo ".env created with production MONGO_URI."

build: clean
	@echo "Building Docker image $(IMAGE_NAME) with BuildKit..."
	DOCKER_BUILDKIT=1 docker build -t $(IMAGE_NAME) .
	@echo "Build complete."

run:
	@echo "Running Docker container $(IMAGE_NAME)..."
	docker run --rm --add-host=host.docker.internal:host-gateway $(IMAGE_NAME)
	@echo "Container stopped."


clean:
	@echo "Cleaning up dangling Docker images and stopped containers..."
	docker image prune -f
	docker container prune -f
	@echo "Cleanup complete."

fclean:
	@echo "Performing a full Docker cleanup (removing all images and containers)..."
	docker system prune -a -f
	@echo "Full cleanup complete."
