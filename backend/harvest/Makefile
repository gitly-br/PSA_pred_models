IMAGE_NAME := harvest-app

.PHONY: build run clean fclean localenv prodenv

localenv:
	@echo "Creating .env for local development..." && \
	if [ -z "$$OPENWEATHER_API_KEY" ]; then \
		echo "Error: OPENWEATHER_API_KEY environment variable is not set. Please set it before running 'make localenv'."; \
		exit 1; \
	fi && \
	echo "MONGO_URI=mongodb://host.docker.internal:27017" > .env && \
	echo "OPENWEATHER_API_KEY=$$OPENWEATHER_API_KEY" >> .env && \
	echo ".env created with local MONGO_URI and OPENWEATHER_API_KEY from your environment."

prodenv:
	@echo "Creating .env for production environment..." && \
	if [ -z "$$MONGO_URI" ]; then \
		echo "Error: MONGO_URI environment variable is not set. Please set it before running 'make prodenv'."; \
		exit 1; \
	fi && \
	if [ -z "$$OPENWEATHER_API_KEY" ]; then \
		echo "Error: OPENWEATHER_API_KEY environment variable is not set. Please set it before running 'make prodenv'."; \
		exit 1; \
	fi && \
	echo "MONGO_URI=$$MONGO_URI" > .env && \
	echo "OPENWEATHER_API_KEY=$$OPENWEATHER_API_KEY" >> .env && \
	echo ".env created with production MONGO_URI and OPENWEATHER_API_KEY."

build: clean
	@echo "Building Docker image $(IMAGE_NAME) with BuildKit..."
	DOCKER_BUILDKIT=1 docker build -t $(IMAGE_NAME) .
	@echo "Build complete."

run:
	@echo "Running Docker container $(IMAGE_NAME)..."
	docker run --rm --add-host=host.docker.internal:host-gateway --env-file .env $(IMAGE_NAME)
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
