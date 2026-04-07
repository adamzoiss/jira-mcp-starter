#!/usr/bin/env bash
# Run the full local unittest suite using the project virtualenv.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Virtual environment not found. Run ./scripts/setup.sh first." >&2
  exit 1
fi

if [[ -f "${ROOT_DIR}/.env" ]]; then
  # Export test-related variables such as live Jira keys when they exist locally.
  set -a
  # shellcheck disable=SC1090
  source "${ROOT_DIR}/.env"
  set +a
fi

# Use unittest discovery so mocked and optional live tests run through one entrypoint.
exec "${VENV_PYTHON}" -m unittest discover -s "${ROOT_DIR}/tests" -p 'test_*.py' -v
