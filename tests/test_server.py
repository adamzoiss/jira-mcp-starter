from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from jira_mcp.server import get_issue, search_issues


class FakeClient:
    def get_issue(self, key: str) -> dict[str, object]:
        return {
            "key": key.upper(),
            "summary": "Mock issue summary",
            "description": "Mock issue description",
            "status": "In Progress",
            "priority": "High",
            "issue_type": "Bug",
            "assignee": "Jane Doe",
            "reporter": "John Smith",
            "labels": ["mock", "test"],
            "components": ["Platform"],
            "fix_versions": ["1.0.0"],
            "last_5_comments": [
                {"author": "User A", "created": "2026-04-06T10:00:00.000-0400", "body": "Looks good."}
            ],
            "linked_issues": [
                {
                    "key": "ABC-456",
                    "summary": "Related mock issue",
                    "status": "To Do",
                    "relationship": "blocks",
                }
            ],
        }

    def search_issues(self, jql: str, max_results: int) -> dict[str, object]:
        return {
            "total": 2,
            "returned_count": min(max_results, 2),
            "issues": [
                {
                    "key": "ABC-123",
                    "summary": f"Mock search result for {jql}",
                    "status": "Open",
                    "issue_type": "Bug",
                    "priority": "Highest",
                    "assignee": "Jane Doe",
                },
                {
                    "key": "ABC-124",
                    "summary": "Second mock result",
                    "status": "In Progress",
                    "issue_type": "Task",
                    "priority": "Medium",
                    "assignee": None,
                },
            ][:max_results],
        }


class ServerToolTests(unittest.TestCase):
    @patch("jira_mcp.server.build_client", return_value=FakeClient())
    def test_get_issue_returns_mocked_issue(self, mock_build_client: MagicMock) -> None:
        result = get_issue("abc-123")

        self.assertEqual(result["key"], "ABC-123")
        self.assertEqual(result["summary"], "Mock issue summary")
        self.assertEqual(result["status"], "In Progress")
        self.assertEqual(result["last_5_comments"][0]["body"], "Looks good.")
        self.assertEqual(result["linked_issues"][0]["relationship"], "blocks")
        mock_build_client.assert_called_once_with()

    @patch("jira_mcp.server.build_client", return_value=FakeClient())
    def test_search_issues_returns_mocked_results(self, mock_build_client: MagicMock) -> None:
        result = search_issues("project = ABC AND status = Open", max_results=1)

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["issues"][0]["key"], "ABC-123")
        self.assertIn("project = ABC", result["issues"][0]["summary"])
        mock_build_client.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
