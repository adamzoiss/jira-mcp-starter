from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import ClassVar

from jira_mcp.jira_client import JiraClient, JiraConfig
from jira_mcp.utils import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class JiraLiveIntegrationTests(unittest.TestCase):
    client: ClassVar[JiraClient]
    issue_key: ClassVar[str]
    test_jql: ClassVar[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.issue_key = os.getenv("JIRA_TEST_ISSUE_KEY", "").strip()
        default_jql = f"issuekey = {cls.issue_key}" if cls.issue_key else ""
        cls.test_jql = os.getenv("JIRA_TEST_JQL", default_jql).strip()
        if not cls.issue_key:
            raise unittest.SkipTest(
                "Set JIRA_TEST_ISSUE_KEY in .env or the shell to run live Jira integration tests."
            )

        cls.client = JiraClient(JiraConfig.from_env())

    def test_get_issue_returns_expected_shape(self) -> None:
        issue = self.client.get_issue(self.issue_key)

        self.assertEqual(issue["key"], self.issue_key)
        self.assertIn("summary", issue)
        self.assertIn("status", issue)
        self.assertIn("issue_type", issue)
        self.assertIn("priority", issue)
        self.assertIn("labels", issue)
        self.assertIn("components", issue)
        self.assertIn("fix_versions", issue)
        self.assertIn("last_5_comments", issue)
        self.assertIn("linked_issues", issue)
        self.assertIsInstance(issue["labels"], list)
        self.assertIsInstance(issue["components"], list)
        self.assertIsInstance(issue["fix_versions"], list)
        self.assertIsInstance(issue["last_5_comments"], list)
        self.assertIsInstance(issue["linked_issues"], list)

    def test_search_issues_returns_expected_shape(self) -> None:
        issues = self.client.search_issues(self.test_jql, max_results=5)

        self.assertIn("total", issues)
        self.assertIn("returned_count", issues)
        self.assertIn("issues", issues)
        self.assertIsInstance(issues["total"], int)
        self.assertIsInstance(issues["returned_count"], int)
        self.assertIsInstance(issues["issues"], list)
        self.assertGreaterEqual(issues["returned_count"], 1)

        first_issue = issues["issues"][0]
        self.assertIn("key", first_issue)
        self.assertIn("summary", first_issue)
        self.assertIn("status", first_issue)
        self.assertIn("issue_type", first_issue)
        self.assertIn("priority", first_issue)
        self.assertIn("assignee", first_issue)


if __name__ == "__main__":
    unittest.main()
