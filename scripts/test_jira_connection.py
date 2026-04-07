#!/usr/bin/env python3
"""Small helper script for validating Jira connectivity outside of MCP clients."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    # Re-exec under the project virtualenv so imports work even without manual activation.
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])

if str(PROJECT_ROOT) not in sys.path:
    # Support running the script directly from the repository checkout.
    sys.path.insert(0, str(PROJECT_ROOT))

from jira_mcp.jira_client import JiraClient, JiraClientError, JiraConfig  # noqa: E402
from jira_mcp.utils import load_dotenv  # noqa: E402


def main() -> int:
    """Load configuration, fetch one issue, and print the structured result."""
    if len(sys.argv) != 2:
        print("Usage: ./scripts/test_jira_connection.py ISSUE-123", file=sys.stderr)
        return 1

    load_dotenv(PROJECT_ROOT / ".env")
    issue_key = sys.argv[1].strip()

    try:
        # Build the same Jira client used by the MCP server so this test mirrors real use.
        client = JiraClient(JiraConfig.from_env())
        issue = client.get_issue(issue_key)
    except (JiraClientError, ValueError) as exc:
        print(f"Connection test failed: {exc}", file=sys.stderr)
        return 1

    print("Connection test succeeded.")
    print(json.dumps(issue, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
