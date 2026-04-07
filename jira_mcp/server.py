from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jira_mcp.jira_client import JiraClient, JiraClientError, JiraConfig  # noqa: E402
from jira_mcp.utils import configure_logging, load_dotenv  # noqa: E402

LOGGER = configure_logging()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

mcp = FastMCP("jira")


def build_client() -> JiraClient:
    load_dotenv(ENV_PATH)
    config = JiraConfig.from_env()
    return JiraClient(config)


@mcp.tool()
def get_issue(key: str) -> dict[str, Any]:
    """Fetch a Jira issue and return a concise structured view."""
    try:
        return build_client().get_issue(key)
    except (JiraClientError, ValueError) as exc:
        LOGGER.error("get_issue failed for %s: %s", key, exc)
        raise RuntimeError(str(exc)) from exc


@mcp.tool()
def search_issues(jql: str, max_results: int = 10) -> dict[str, Any]:
    """Search Jira issues by JQL and return structured summaries."""
    try:
        return build_client().search_issues(jql=jql, max_results=max_results)
    except (JiraClientError, ValueError) as exc:
        LOGGER.error("search_issues failed: %s", exc)
        raise RuntimeError(str(exc)) from exc


if __name__ == "__main__":
    LOGGER.info("Starting Jira MCP server over stdio.")
    mcp.run(transport="stdio")
