# Makefile for environment management

.PHONY: envs local dev prod help

# Default target
help:
	@echo "Available targets:"
	@echo "  envs  - Create environment files from .env.example"
	@echo "  local - Load local environment variables"
	@echo "  dev   - Load development environment variables"
	@echo "  prod  - Load production environment variables"
	@echo "  help  - Show this help message"

# Create environment files from template
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

# Load local environment
local:
	@if [ ! -f .env.local ]; then \
		echo "❌ .env.local not found. Run 'make envs' first."; \
		exit 1; \
	fi
	@echo "Loading local environment..."
	@export $$(grep -v '^#' .env.local | xargs)

# Load development environment
dev:
	@if [ ! -f .env.dev ]; then \
		echo "❌ .env.dev not found. Run 'make envs' first."; \
		exit 1; \
	fi
	@echo "Loading development environment..."
	@export $$(grep -v '^#' .env.dev | xargs)

# Load production environment
prod:
	@if [ ! -f .env.prod ]; then \
		echo "❌ .env.prod not found. Run 'make envs' first."; \
		exit 1; \
	fi
	@echo "Loading production environment..."
	@export $$(grep -v '^#' .env.prod | xargs)
