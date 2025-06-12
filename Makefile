SHELL := /bin/bash

.PHONY: help dev-frontend dev-backend dev install-backend test-agent

help:
	@echo "Available commands:"
	@echo "  make dev-frontend    - Starts the frontend development server (Vite)"
	@echo "  make dev-backend     - Starts the Gemini backend development server (FastAPI)"
	@echo "  make dev             - Starts both frontend and backend development servers"
	@echo "  make install-backend - Install backend dependencies"
	@echo "  make test-agent      - Test the ADK research agent"
	@echo "  make test-tavily     - Test Tavily Search integration"

install-backend:
	@echo "Installing Gemini backend dependencies..."
	@cd backend && source .venv/bin/activate && pip install -e .

dev-frontend:
	@echo "Starting frontend development server..."
	@cd frontend && npm run dev

dev-backend:
	@echo "Starting Gemini backend development server..."
	@cd backend && source .venv/bin/activate && python -m uvicorn src.agent.server:app --host 0.0.0.0 --port 2024 --reload

test-agent:
	@echo "Testing ADK research agent..."
	@cd backend && source .venv/bin/activate && python test_adk_agent.py

test-tavily:
	@echo "Testing Tavily Search integration..."
	@cd backend && source .venv/bin/activate && python test_tavily_search.py

# Run frontend and backend concurrently
dev:
	@echo "Starting both frontend and Gemini backend development servers..."
	@make dev-frontend & make dev-backend 