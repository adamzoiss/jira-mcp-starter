from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar, cast

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from jira_mcp.utils import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class JiraMcpLiveIntegrationTests(unittest.TestCase):
    issue_key: ClassVar[str]
    test_jql: ClassVar[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.issue_key = os.getenv("JIRA_TEST_ISSUE_KEY", "").strip()
        default_jql = f"issuekey = {cls.issue_key}" if cls.issue_key else ""
        cls.test_jql = os.getenv("JIRA_TEST_JQL", default_jql).strip()
        if not cls.issue_key:
            raise unittest.SkipTest(
                "Set JIRA_TEST_ISSUE_KEY in .env or the shell to run live MCP transport tests."
            )

    def test_mcp_server_lists_expected_tools(self) -> None:
        tool_names = anyio.run(self._list_tool_names)
        self.assertIn("get_issue", tool_names)
        self.assertIn("search_issues", tool_names)

    def test_mcp_get_issue_returns_expected_shape(self) -> None:
        result = anyio.run(self._call_tool, "get_issue", {"key": self.issue_key})

        self.assertEqual(result["key"], self.issue_key)
        self.assertIn("summary", result)
        self.assertIn("status", result)
        self.assertIn("issue_type", result)
        self.assertIn("priority", result)
        self.assertIn("labels", result)
        self.assertIn("components", result)
        self.assertIn("fix_versions", result)
        self.assertIn("last_5_comments", result)
        self.assertIn("linked_issues", result)

    def test_mcp_search_issues_returns_expected_shape(self) -> None:
        result = anyio.run(self._call_tool, "search_issues", {"jql": self.test_jql, "max_results": 5})

        self.assertIn("total", result)
        self.assertIn("returned_count", result)
        self.assertIn("issues", result)
        self.assertIsInstance(result["issues"], list)
        self.assertGreaterEqual(result["returned_count"], 1)

        first_issue = result["issues"][0]
        self.assertIn("key", first_issue)
        self.assertIn("summary", first_issue)
        self.assertIn("status", first_issue)
        self.assertIn("issue_type", first_issue)
        self.assertIn("priority", first_issue)
        self.assertIn("assignee", first_issue)

    @classmethod
    async def _list_tool_names(cls) -> list[str]:
        async with cls._client_session() as session:
            result = await session.list_tools()
            return [tool.name for tool in result.tools]

    @classmethod
    async def _call_tool(cls, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with cls._client_session() as session:
            result = await session.call_tool(tool_name, arguments)

        if result.isError:
            raise AssertionError(f"MCP tool call returned an error: {result}")
        if result.structuredContent is None:
            raise AssertionError("Expected structuredContent from MCP tool result.")
        return cast(dict[str, Any], result.structuredContent)

    @classmethod
    def _server_parameters(cls) -> StdioServerParameters:
        env = {
            "JIRA_BASE_URL": os.environ["JIRA_BASE_URL"],
            "JIRA_USER": os.environ["JIRA_USER"],
            "JIRA_TOKEN": os.environ["JIRA_TOKEN"],
        }

        for optional_name in (
            "JIRA_VERIFY_TLS",
            "JIRA_TIMEOUT_SECONDS",
            "JIRA_MAX_RETRIES",
            "REQUESTS_CA_BUNDLE",
        ):
            value = os.getenv(optional_name)
            if value:
                env[optional_name] = value

        return StdioServerParameters(
            command=sys.executable,
            args=[str(PROJECT_ROOT / "jira_mcp" / "server.py")],
            env=env,
            cwd=PROJECT_ROOT,
        )

    @classmethod
    def _client_session(cls) -> "_ClientSessionContext":
        return _ClientSessionContext(cls._server_parameters())


class _ClientSessionContext:
    def __init__(self, server_params: StdioServerParameters) -> None:
        self.server_params = server_params

    async def __aenter__(self) -> ClientSession:
        self._stdio_context = stdio_client(self.server_params)
        read_stream, write_stream = await self._stdio_context.__aenter__()
        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()
        return self._session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._session.__aexit__(exc_type, exc, tb)
        await self._stdio_context.__aexit__(exc_type, exc, tb)


if __name__ == "__main__":
    unittest.main()
