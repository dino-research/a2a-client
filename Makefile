SHELL := /bin/bash

.PHONY: help dev-frontend dev-backend dev install-backend test-coordinator test-llm-reasoning

help:
	@echo "Available commands:"
	@echo "  make dev-frontend      - Starts the frontend development server (Vite)"
	@echo "  make dev-backend       - Starts the Gemini backend development server (FastAPI)"
	@echo "  make dev               - Starts both frontend and backend development servers"
	@echo "  make install-backend   - Install backend dependencies"
	@echo "  make test-coordinator  - Test the coordinator agent functionality"
	@echo "  make test-llm-reasoning - Test LLM reasoning capability for classification"

install-backend:
	@echo "Installing Gemini backend dependencies..."
	@cd backend && source .venv/bin/activate && pip install -e .

dev-frontend:
	@echo "Starting frontend development server..."
	@cd frontend && npm run dev

dev-backend:
	@echo "Starting Gemini backend development server..."
	@cd backend && source .venv/bin/activate && python -m uvicorn src.agent.server:app --host 0.0.0.0 --port 2024 --reload

test-coordinator:
	@echo "Testing coordinator agent functionality..."
	@cd backend && source .venv/bin/activate && python test_coordinator.py

test-llm-reasoning:
	@echo "Testing LLM reasoning capability..."
	@cd backend && source .venv/bin/activate && python test_llm_reasoning.py

# Run frontend and backend concurrently
dev:
	@echo "Starting both frontend and Gemini backend development servers..."
	@make dev-frontend & make dev-backend 