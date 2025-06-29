IMAGE_NAME := floodcast-app

.PHONY: build run clean fclean

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
