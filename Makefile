# Makefile for environment management

SHELL := /bin/bash
.PHONY: env envs local dev prod help bootstrap-local-weather

# Default target
help:
	@echo "Available targets:"
	@echo "  env   - Generate .env from .env.local"
	@echo "  envs  - Create environment files from .env.example"
	@echo "  local - Source local environment variables"
	@echo "  dev   - Source development environment variables"
	@echo "  prod  - Source production environment variables"
	@echo "  bootstrap-local-weather - Seed MinIO and bootstrap api_data"
	@echo "  help  - Show this help message"

# Create environment files from template
env:
	@if [ ! -f .env.local ]; then \
		echo "Missing .env.local"; \
		exit 1; \
	fi
	@sed 's/^export //' .env.local > .env
	@echo "✓ Generated .env from .env.local"

envs:
	@echo "Creating environment files from .env.example..."
	@if [ ! -f .env.local ]; then \
		cp .env.example .env.local && \
		echo "✓ Created .env.local"; \
	else \
		echo "⚠ .env.local already exists, skipping"; \
	fi
	@if [ ! -f .env.dev ]; then \
		cp .env.example .env.dev && \
		echo "✓ Created .env.dev"; \
	else \
		echo "⚠ .env.dev already exists, skipping"; \
	fi
	@if [ ! -f .env.prod ]; then \
		cp .env.example .env.prod && \
		echo "✓ Created .env.prod"; \
	else \
		echo "⚠ .env.prod already exists, skipping"; \
	fi
	@echo "Done! Please edit the environment files with your actual values."
	@echo "After that, just use source .env.local/dev/prod to source the variables"

bootstrap-local-weather:
	@PYTHONPATH=backend/harvest uv run --with pytest --with polars --with minio --with motor --with pymongo python -m harvest.bootstrap_local_weather
