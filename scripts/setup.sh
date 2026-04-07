#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found on PATH." >&2
  exit 1
fi

echo "Creating virtual environment in ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"

echo "Installing Python dependencies"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/pip" install -e "${ROOT_DIR}[dev]"

cat <<EOF

Setup complete.

Next steps:
1. Copy .env.example to .env
2. Fill in your Jira connection settings
3. Test the connection:
   ./scripts/test_jira_connection.py ISSUE-123
4. Start the MCP server:
   ./scripts/run.sh
5. Register it with Codex:
   codex mcp add jira -- ./scripts/run.sh
6. Run linting and type checks:
   make lint
   make typecheck
EOF
