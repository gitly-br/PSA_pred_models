IMAGE_NAME := backend
CONTAINER_NAME := backend-app

.PHONY: build run stop logs clean fclean test

build: stop clean
	@echo "Building Docker image $(IMAGE_NAME) with BuildKit..."
	DOCKER_BUILDKIT=1 docker build -t $(IMAGE_NAME) .
	@echo "Build complete."

run: build stop
	@echo "Running Docker container $(IMAGE_NAME)..."
	docker run -d -p 8000:8000 --rm --add-host=host.docker.internal:host-gateway --name $(CONTAINER_NAME) -e NODE_ENV=local $(IMAGE_NAME)
	@echo "Container started."

stop:
	@echo "Stopping Docker container $(CONTAINER_NAME)..."
	-docker stop $(CONTAINER_NAME) 2>/dev/null || true
	@echo "Container stopped."


logs:
	@echo "Showing logs for Docker container $(CONTAINER_NAME)..."
	docker logs -f $(CONTAINER_NAME)

clean:
	@echo "Cleaning up dangling Docker images and stopped containers..."
	docker image prune -f
	docker container prune -f
	@echo "Cleanup complete."

fclean:
	@echo "Performing a full Docker cleanup (removing all images and containers)..."
	docker system prune -a -f
	@echo "Full cleanup complete."

test:
	@echo "Testing the API with curl..."
	curl http://localhost:8000/region/santoandre
