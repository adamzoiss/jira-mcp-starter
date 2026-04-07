#!/usr/bin/env bash
# Start the MCP server using the local virtualenv and optional .env configuration.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

# On Windows (Git Bash/MINGW, MSYS2, or Cygwin) Python creates Scripts\ instead of bin/.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    VENV_PYTHON="${ROOT_DIR}/.venv/Scripts/python.exe"
    ;;
  *)
    VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
    ;;
esac

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Virtual environment not found. Run ./scripts/setup.sh first." >&2
  exit 1
fi

if [[ -f "${ENV_FILE}" ]]; then
  # Export .env values into the current shell so the Python process can read them.
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

# Replace the shell with the MCP server process so signals propagate cleanly.
exec "${VENV_PYTHON}" "${ROOT_DIR}/jira_mcp/server.py"
