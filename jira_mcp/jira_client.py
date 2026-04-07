"""Jira REST client and response-shaping logic used by the MCP tools."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from requests import Response, Session
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

from jira_mcp.utils import (
    clean_text,
    configure_logging,
    get_nested,
    parse_bool,
    require_env,
)

LOGGER = configure_logging()


class JiraClientError(RuntimeError):
    """Base error for Jira client failures."""


class JiraAuthenticationError(JiraClientError):
    """Raised for Jira authentication and authorization failures."""


class JiraNotFoundError(JiraClientError):
    """Raised when a Jira resource does not exist."""


class JiraResponseError(JiraClientError):
    """Raised when Jira returns an invalid or unexpected response."""


class JiraRequestValidationError(JiraClientError):
    """Raised for non-retryable Jira 4xx request failures."""


@dataclass(frozen=True)
class JiraConfig:
    """Normalized runtime configuration for Jira connectivity."""

    base_url: str
    user: str
    token: str
    verify_tls: bool = True
    timeout_seconds: int = 15
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "JiraConfig":
        """Build configuration from environment variables with validation."""
        verify_tls = parse_bool(value=require_env_optional("JIRA_VERIFY_TLS"), default=True)
        timeout_seconds = parse_positive_int(
            name="JIRA_TIMEOUT_SECONDS",
            value=require_env_optional("JIRA_TIMEOUT_SECONDS"),
            default=15,
        )
        max_retries = parse_non_negative_int(
            name="JIRA_MAX_RETRIES",
            value=require_env_optional("JIRA_MAX_RETRIES"),
            default=2,
        )
        return cls(
            base_url=require_env("JIRA_BASE_URL").rstrip("/"),
            user=require_env("JIRA_USER"),
            token=require_env("JIRA_TOKEN"),
            verify_tls=verify_tls,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )


def require_env_optional(name: str) -> str | None:
    """Read an optional environment variable and strip surrounding whitespace."""
    value = os.getenv(name)
    return value.strip() if value else None


def parse_positive_int(name: str, value: str | None, default: int) -> int:
    """Parse a positive integer environment variable or raise a clear error."""
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return parsed


def parse_non_negative_int(name: str, value: str | None, default: int) -> int:
    """Parse a non-negative integer environment variable or raise a clear error."""
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a non-negative integer.") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return parsed


class JiraClient:
    """Small Jira REST client focused on the MCP tools used by this project."""

    def __init__(self, config: JiraConfig) -> None:
        self.config = config
        self.session = self._build_session(config)

    def _build_session(self, config: JiraConfig) -> Session:
        """Create a configured requests session for repeated Jira API calls."""
        session = requests.Session()
        session.auth = HTTPBasicAuth(config.user, config.token)
        session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "jira-mcp-starter/1.0",
            }
        )
        session.verify = config.verify_tls
        if not config.verify_tls:
            disable_warnings(InsecureRequestWarning)
            LOGGER.warning("TLS certificate verification is disabled for Jira requests.")
        return session

    def get_issue(self, key: str) -> dict[str, Any]:
        """Fetch one issue and reduce the large Jira payload into a compact shape."""
        normalized_key = key.strip().upper()
        if not normalized_key:
            raise ValueError("Issue key must not be empty.")

        # Limit the fields we request so the MCP response stays concise and predictable.
        fields = ",".join(
            [
                "summary",
                "description",
                "status",
                "priority",
                "issuetype",
                "assignee",
                "reporter",
                "labels",
                "components",
                "fixVersions",
                "comment",
                "issuelinks",
            ]
        )
        payload = self._request_json(
            "GET",
            f"/rest/api/2/issue/{normalized_key}",
            params={"fields": fields},
        )
        return self._serialize_issue_detail(payload)

    def search_issues(self, jql: str, max_results: int = 10) -> dict[str, Any]:
        """Run a JQL search and return a compact list of issue summaries."""
        normalized_jql = jql.strip()
        if not normalized_jql:
            raise ValueError("JQL must not be empty.")

        # Keep search result sizes bounded even if the caller asks for more.
        capped_results = max(1, min(max_results, 100))
        payload = self._request_json(
            "GET",
            "/rest/api/2/search",
            params={
                "jql": normalized_jql,
                "maxResults": capped_results,
                "fields": "summary,status,issuetype,priority,assignee",
            },
        )

        issues = payload.get("issues")
        if not isinstance(issues, list):
            raise JiraResponseError("Jira search response did not include a valid issues list.")

        return {
            "total": self._coerce_int(payload.get("total")),
            "returned_count": len(issues),
            "issues": [self._serialize_issue_summary(issue) for issue in issues],
        }

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a Jira request with retries, timeout handling, and JSON parsing."""
        url = f"{self.config.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                # All requests use an explicit timeout so the MCP server cannot hang forever.
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    timeout=self.config.timeout_seconds,
                )
                self._raise_for_status(response)
                return self._parse_json(response)
            except (RequestException, JiraClientError, ValueError) as exc:
                last_error = exc
                should_retry = attempt < self.config.max_retries and self._is_retryable(exc)
                if should_retry:
                    # Use a tiny linear backoff to smooth over transient network hiccups.
                    sleep_seconds = 0.5 * (attempt + 1)
                    LOGGER.warning(
                        "Jira request failed on attempt %s/%s: %s. Retrying in %.1fs.",
                        attempt + 1,
                        self.config.max_retries + 1,
                        exc,
                        sleep_seconds,
                    )
                    time.sleep(sleep_seconds)
                    continue
                break

        if isinstance(last_error, Exception):
            raise last_error
        raise JiraClientError("Jira request failed for an unknown reason.")

    def _raise_for_status(self, response: Response) -> None:
        """Translate Jira HTTP status codes into more meaningful client exceptions."""
        status_code = response.status_code
        if 200 <= status_code < 300:
            return

        message = self._extract_error_message(response)
        if status_code in {401, 403}:
            raise JiraAuthenticationError(
                f"Jira authentication failed with status {status_code}: {message}"
            )
        if status_code == 404:
            raise JiraNotFoundError(f"Jira resource not found: {message}")
        if status_code == 429:
            raise JiraClientError(f"Jira rate limit reached with status {status_code}: {message}")
        if 400 <= status_code < 500:
            raise JiraRequestValidationError(
                f"Jira request failed with status {status_code}: {message}"
            )
        if 500 <= status_code < 600:
            raise JiraClientError(f"Jira server error {status_code}: {message}")
        raise JiraClientError(f"Unexpected Jira response status {status_code}: {message}")

    def _extract_error_message(self, response: Response) -> str:
        """Pull the most useful human-readable error string from a Jira response."""
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text or "No additional error details were returned."

        if isinstance(payload, dict):
            errors = payload.get("errorMessages")
            if isinstance(errors, list) and errors:
                return "; ".join(str(item) for item in errors)
            error_map = payload.get("errors")
            if isinstance(error_map, dict) and error_map:
                return "; ".join(f"{key}: {value}" for key, value in error_map.items())
        return "No additional error details were returned."

    def _parse_json(self, response: Response) -> dict[str, Any]:
        """Parse and validate the top-level Jira JSON response object."""
        try:
            payload = response.json()
        except ValueError as exc:
            raise JiraResponseError("Jira response did not contain valid JSON.") from exc

        if not isinstance(payload, dict):
            raise JiraResponseError("Jira response JSON was not an object.")
        return payload

    def _is_retryable(self, exc: Exception) -> bool:
        """Retry only failures that are likely transient rather than caller mistakes."""
        if isinstance(
            exc,
            JiraAuthenticationError | JiraNotFoundError | JiraRequestValidationError | ValueError,
        ):
            return False
        if isinstance(exc, JiraClientError):
            return True
        return isinstance(exc, RequestException)

    def _serialize_issue_detail(self, issue: dict[str, Any]) -> dict[str, Any]:
        """Transform a raw issue payload into the MCP-facing detail structure."""
        fields = issue.get("fields")
        if not isinstance(fields, dict):
            raise JiraResponseError("Jira issue response did not include valid fields.")

        comments = get_nested(fields, "comment", "comments")
        if not isinstance(comments, list):
            comments = []

        issue_links = fields.get("issuelinks")
        if not isinstance(issue_links, list):
            issue_links = []

        return {
            # Every field access is defensive because Jira Server/Data Center instances vary.
            "key": clean_text(issue.get("key")),
            "summary": clean_text(fields.get("summary")),
            "description": self._extract_description(fields.get("description")),
            "status": clean_text(get_nested(fields, "status", "name")),
            "priority": clean_text(get_nested(fields, "priority", "name")),
            "issue_type": clean_text(get_nested(fields, "issuetype", "name")),
            "assignee": self._extract_user_display(fields.get("assignee")),
            "reporter": self._extract_user_display(fields.get("reporter")),
            "labels": self._extract_string_list(fields.get("labels")),
            "components": self._extract_named_items(fields.get("components")),
            "fix_versions": self._extract_named_items(fields.get("fixVersions")),
            "last_5_comments": [self._serialize_comment(comment) for comment in comments[-5:]],
            "linked_issues": [
                serialized
                for link in issue_links
                if (serialized := self._serialize_issue_link(link)) is not None
            ],
        }

    def _serialize_issue_summary(self, issue: dict[str, Any]) -> dict[str, Any]:
        """Transform a search result issue into the lighter-weight list shape."""
        fields = issue.get("fields")
        if not isinstance(fields, dict):
            raise JiraResponseError("Jira search issue did not include valid fields.")

        return {
            "key": clean_text(issue.get("key")),
            "summary": clean_text(fields.get("summary")),
            "status": clean_text(get_nested(fields, "status", "name")),
            "issue_type": clean_text(get_nested(fields, "issuetype", "name")),
            "priority": clean_text(get_nested(fields, "priority", "name")),
            "assignee": self._extract_user_display(fields.get("assignee")),
        }

    def _serialize_comment(self, comment: dict[str, Any]) -> dict[str, Any]:
        """Normalize a Jira comment into the subset of fields exposed by the MCP tool."""
        return {
            "author": self._extract_user_display(comment.get("author")),
            "created": clean_text(comment.get("created")),
            "body": self._extract_description(comment.get("body")),
        }

    def _serialize_issue_link(self, link: dict[str, Any]) -> dict[str, Any] | None:
        """Normalize one Jira issue link regardless of inward/outward direction."""
        link_type = link.get("type")
        relationship = self._extract_link_relationship(link_type, "outward")
        linked_issue = link.get("outwardIssue")
        if linked_issue is None:
            relationship = self._extract_link_relationship(link_type, "inward")
            linked_issue = link.get("inwardIssue")

        if not isinstance(linked_issue, dict):
            return None

        fields = linked_issue.get("fields")
        if not isinstance(fields, dict):
            fields = {}

        return {
            "relationship": relationship,
            "key": clean_text(linked_issue.get("key")),
            "summary": clean_text(fields.get("summary")),
            "status": clean_text(get_nested(fields, "status", "name")),
        }

    def _extract_link_relationship(
        self,
        link_type: Any,
        direction: str,
    ) -> str | None:
        """Choose the best available relationship label for an issue link."""
        if not isinstance(link_type, dict):
            return None
        return clean_text(link_type.get(direction)) or clean_text(link_type.get("name"))

    def _extract_description(self, value: Any) -> str | None:
        """Flatten Jira description fields across string, rich-text, and list shapes."""
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            return self._flatten_rich_text(value)
        if isinstance(value, list):
            parts = [self._extract_description(item) for item in value]
            filtered = [part for part in parts if part]
            return "\n".join(filtered) if filtered else None
        return str(value)

    def _flatten_rich_text(self, value: dict[str, Any]) -> str | None:
        """Walk Jira rich-text structures and collect text into a plain string."""
        texts: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, str):
                stripped = node.strip()
                if stripped:
                    texts.append(stripped)
                return
            if isinstance(node, list):
                for item in node:
                    walk(item)
                return
            if not isinstance(node, dict):
                return

            if "text" in node and isinstance(node["text"], str):
                stripped = node["text"].strip()
                if stripped:
                    texts.append(stripped)
            # Jira rich text varies by deployment/version, so walk a few common child keys.
            for child_key in ("content", "paragraphs", "items"):
                child = node.get(child_key)
                if child is not None:
                    walk(child)

        walk(value)
        if not texts:
            return None
        return "\n".join(texts)

    def _extract_user_display(self, value: Any) -> str | None:
        """Return the most useful display string for a Jira user-like object."""
        if not isinstance(value, dict):
            return None
        return (
            clean_text(value.get("displayName"))
            or clean_text(value.get("name"))
            or clean_text(value.get("emailAddress"))
        )

    def _extract_named_items(self, values: Any) -> list[str]:
        """Extract `.name` from Jira arrays like components or fixVersions."""
        if not isinstance(values, list):
            return []
        output: list[str] = []
        for item in values:
            if not isinstance(item, dict):
                continue
            name = clean_text(item.get("name"))
            if name:
                output.append(name)
        return output

    def _extract_string_list(self, values: Any) -> list[str]:
        """Normalize a list of raw label-like values into strings."""
        if not isinstance(values, list):
            return []
        output: list[str] = []
        for item in values:
            text = clean_text(item)
            if text:
                output.append(text)
        return output

    def _coerce_int(self, value: Any) -> int:
        """Best-effort integer conversion with a safe zero fallback."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
