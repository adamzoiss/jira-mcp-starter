from __future__ import annotations

import os
import unittest
from typing import Any, cast
from unittest.mock import Mock, patch

from requests.exceptions import ConnectTimeout

from jira_mcp.jira_client import (
    JiraAuthenticationError,
    JiraClient,
    JiraConfig,
    JiraNotFoundError,
    JiraRequestValidationError,
)


def build_response(status_code: int, payload: dict | None = None, text: str = "") -> Mock:
    response = Mock()
    response.status_code = status_code
    response.text = text
    if payload is None:
        response.json.side_effect = ValueError("No JSON")
    else:
        response.json.return_value = payload
    return response


class JiraClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = JiraClient(
            JiraConfig(
                base_url="https://jira.example.com",
                user="user",
                token="token",
                verify_tls=True,
            )
        )

    def set_request_mock(self, request_mock: Mock) -> Mock:
        session = cast(Any, self.client.session)
        session.request = request_mock
        return request_mock

    def test_get_issue_returns_structured_output(self) -> None:
        self.set_request_mock(
            Mock(
            return_value=build_response(
                200,
                {
                    "key": "ABC-123",
                    "fields": {
                        "summary": "Fix login failure",
                        "description": "Users cannot log in",
                        "status": {"name": "In Progress"},
                        "priority": {"name": "High"},
                        "issuetype": {"name": "Bug"},
                        "assignee": {"displayName": "Jane Doe"},
                        "reporter": {"displayName": "John Smith"},
                        "labels": ["customer", "prod"],
                        "components": [{"name": "Auth"}],
                        "fixVersions": [{"name": "2026.04"}],
                        "comment": {
                            "comments": [
                                {"author": {"displayName": "User A"}, "created": "2026-04-01", "body": "One"},
                                {"author": {"displayName": "User B"}, "created": "2026-04-02", "body": "Two"},
                                {"author": {"displayName": "User C"}, "created": "2026-04-03", "body": "Three"},
                                {"author": {"displayName": "User D"}, "created": "2026-04-04", "body": "Four"},
                                {"author": {"displayName": "User E"}, "created": "2026-04-05", "body": "Five"},
                                {"author": {"displayName": "User F"}, "created": "2026-04-06", "body": "Six"},
                            ]
                        },
                        "issuelinks": [
                            {
                                "type": {"outward": "blocks"},
                                "outwardIssue": {
                                    "key": "ABC-200",
                                    "fields": {
                                        "summary": "Release is blocked",
                                        "status": {"name": "To Do"},
                                    },
                                },
                            }
                        ],
                    },
                },
            )
            )
        )

        result = self.client.get_issue("abc-123")

        self.assertEqual(result["key"], "ABC-123")
        self.assertEqual(result["summary"], "Fix login failure")
        self.assertEqual(result["status"], "In Progress")
        self.assertEqual(result["priority"], "High")
        self.assertEqual(result["issue_type"], "Bug")
        self.assertEqual(result["assignee"], "Jane Doe")
        self.assertEqual(result["reporter"], "John Smith")
        self.assertEqual(result["labels"], ["customer", "prod"])
        self.assertEqual(result["components"], ["Auth"])
        self.assertEqual(result["fix_versions"], ["2026.04"])
        self.assertEqual(len(result["last_5_comments"]), 5)
        self.assertEqual(result["last_5_comments"][0]["body"], "Two")
        self.assertEqual(
            result["linked_issues"],
            [
                {
                    "relationship": "blocks",
                    "key": "ABC-200",
                    "summary": "Release is blocked",
                    "status": "To Do",
                }
            ],
        )

    def test_search_issues_returns_structured_summaries(self) -> None:
        request_mock = self.set_request_mock(
            Mock(
            return_value=build_response(
                200,
                {
                    "total": 1,
                    "issues": [
                        {
                            "key": "ABC-123",
                            "fields": {
                                "summary": "Fix login failure",
                                "status": {"name": "Done"},
                                "issuetype": {"name": "Bug"},
                                "priority": {"name": "Highest"},
                                "assignee": {"displayName": "Jane Doe"},
                            },
                        }
                    ],
                },
            )
            )
        )

        result = self.client.search_issues("project = ABC", max_results=500)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["issues"][0]["key"], "ABC-123")
        _, kwargs = request_mock.call_args
        self.assertEqual(kwargs["params"]["maxResults"], 100)

    def test_retries_transient_network_failures(self) -> None:
        request_mock = self.set_request_mock(
            Mock(
            side_effect=[
                ConnectTimeout("timed out"),
                build_response(200, {"total": 0, "issues": []}),
            ]
            )
        )

        result = self.client.search_issues("project = ABC", max_results=10)

        self.assertEqual(result["returned_count"], 0)
        self.assertEqual(request_mock.call_count, 2)

    def test_does_not_retry_not_found(self) -> None:
        request_mock = self.set_request_mock(
            Mock(
            return_value=build_response(404, {"errorMessages": ["Issue does not exist"]})
            )
        )

        with self.assertRaises(JiraNotFoundError):
            self.client.get_issue("ABC-404")

        self.assertEqual(request_mock.call_count, 1)

    def test_does_not_retry_bad_request(self) -> None:
        request_mock = self.set_request_mock(
            Mock(
            return_value=build_response(400, {"errorMessages": ["The value 'bad' does not exist"]})
            )
        )

        with self.assertRaises(JiraRequestValidationError):
            self.client.search_issues("bad jql", max_results=10)

        self.assertEqual(request_mock.call_count, 1)

    def test_authentication_error_is_raised(self) -> None:
        self.set_request_mock(
            Mock(return_value=build_response(401, {"errorMessages": ["Login failed"]}))
        )

        with self.assertRaises(JiraAuthenticationError):
            self.client.get_issue("ABC-123")

    def test_missing_fields_are_handled_gracefully(self) -> None:
        self.set_request_mock(
            Mock(
            return_value=build_response(
                200,
                {
                    "key": "ABC-1",
                    "fields": {
                        "summary": None,
                        "description": None,
                        "status": {},
                        "priority": None,
                        "issuetype": None,
                        "labels": None,
                        "components": None,
                        "fixVersions": None,
                        "comment": {"comments": []},
                        "issuelinks": [],
                    },
                },
            )
            )
        )

        result = self.client.get_issue("ABC-1")

        self.assertIsNone(result["summary"])
        self.assertIsNone(result["description"])
        self.assertIsNone(result["status"])
        self.assertEqual(result["labels"], [])
        self.assertEqual(result["components"], [])
        self.assertEqual(result["fix_versions"], [])
        self.assertEqual(result["last_5_comments"], [])
        self.assertEqual(result["linked_issues"], [])

    @patch.dict(
        os.environ,
        {
            "JIRA_BASE_URL": "https://jira.example.com",
            "JIRA_USER": "user",
            "JIRA_TOKEN": "token",
            "JIRA_VERIFY_TLS": "true",
            "JIRA_TIMEOUT_SECONDS": "25",
            "JIRA_MAX_RETRIES": "4",
        },
        clear=False,
    )
    def test_config_from_env_uses_timeout_and_retry_overrides(self) -> None:
        config = JiraConfig.from_env()

        self.assertEqual(config.timeout_seconds, 25)
        self.assertEqual(config.max_retries, 4)

    @patch.dict(
        os.environ,
        {
            "JIRA_BASE_URL": "https://jira.example.com",
            "JIRA_USER": "user",
            "JIRA_TOKEN": "token",
            "JIRA_TIMEOUT_SECONDS": "0",
        },
        clear=False,
    )
    def test_config_from_env_rejects_non_positive_timeout(self) -> None:
        with self.assertRaises(ValueError):
            JiraConfig.from_env()

    @patch.dict(
        os.environ,
        {
            "JIRA_BASE_URL": "https://jira.example.com",
            "JIRA_USER": "user",
            "JIRA_TOKEN": "token",
            "JIRA_MAX_RETRIES": "-1",
        },
        clear=False,
    )
    def test_config_from_env_rejects_negative_retries(self) -> None:
        with self.assertRaises(ValueError):
            JiraConfig.from_env()


if __name__ == "__main__":
    unittest.main()
