.DEFAULT_GOAL := help
SHELL := /bin/bash

ROOT_DIR := $(CURDIR)
VENV_DIR := $(ROOT_DIR)/.venv
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

.PHONY: help setup venv install run test test-live connection-test clean

help:
	@echo "Available targets:"
	@echo "  make setup                    Create .venv and install dependencies"
	@echo "  make venv                     Create .venv and upgrade pip"
	@echo "  make install                  Install Python dependencies into .venv"
	@echo "  make run                      Start the Jira MCP server"
	@echo "  make test                     Run mocked tests and optional live tests"
	@echo "  make test-live                Run only the live Jira integration tests"
	@echo "  make connection-test ISSUE=ABC-123"
	@echo "                               Validate Jira connectivity with one issue"
	@echo "  make clean                    Remove local Python cache artifacts"

setup:
	./scripts/setup.sh

venv:
	@if [[ ! -x "$(VENV_PYTHON)" ]]; then \
		echo "Creating virtual environment in $(VENV_DIR)"; \
		python3 -m venv "$(VENV_DIR)"; \
	fi
	"$(VENV_PYTHON)" -m pip install --upgrade pip

install: venv
	"$(VENV_PIP)" install -r "$(ROOT_DIR)/requirements.txt"

run:
	./scripts/run.sh

test:
	./scripts/run_tests.sh

test-live:
	@if [[ ! -x "$(VENV_PYTHON)" ]]; then \
		echo "Virtual environment not found. Run 'make setup' first." >&2; \
		exit 1; \
	fi
	@if [[ -f "$(ROOT_DIR)/.env" ]]; then \
		set -a; \
		source "$(ROOT_DIR)/.env"; \
		set +a; \
	fi; \
	exec "$(VENV_PYTHON)" -m unittest tests.test_live_jira -v

connection-test:
	@if [[ -z "$(ISSUE)" ]]; then \
		echo "Usage: make connection-test ISSUE=ABC-123" >&2; \
		exit 1; \
	fi
	./scripts/test_jira_connection.py "$(ISSUE)"

clean:
	find "$(ROOT_DIR)" \
		\( -path "$(ROOT_DIR)/.git" -o -path "$(ROOT_DIR)/.venv" \) -prune -o \
		\( -name '__pycache__' -o -name '.pytest_cache' \) -type d -exec rm -rf {} +
	find "$(ROOT_DIR)" -name '*.pyc' -delete

