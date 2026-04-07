"""Shared utility helpers used by the Jira client, MCP server, and scripts."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

LOGGER_NAME = "jira_mcp"


def configure_logging() -> logging.Logger:
    """Configure process-wide logging to stderr for MCP-safe output."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        # Reuse the existing logger configuration so repeated imports stay idempotent.
        return logger

    # MCP servers must keep stdout clean for protocol messages, so logs stay on stderr.
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def parse_bool(value: str | None, default: bool = True) -> bool:
    """Parse a typical environment-variable boolean with a safe fallback."""
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def load_dotenv(dotenv_path: Path) -> None:
    """Load simple KEY=VALUE pairs from a local .env file into os.environ."""
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # Ignore comments, blank lines, and malformed entries instead of failing hard.
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Keep explicitly exported environment variables authoritative over .env values.
        if not key or key in os.environ:
            continue

        # Support simple quoted values without needing an external dotenv dependency.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ[key] = value


def require_env(name: str) -> str:
    """Return a required environment variable or raise a clear configuration error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"Missing required environment variable: {name}. "
            "Set it in your shell or .env file before starting the Jira MCP server."
        )
    return value


def clean_text(value: Any) -> str | None:
    """Normalize optional values into stripped strings or None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return str(value)


def get_nested(data: dict[str, Any], *keys: str) -> Any:
    """Safely traverse nested dictionaries without raising KeyError/TypeError."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current
