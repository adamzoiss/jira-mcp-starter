# Jira MCP Starter

## Overview

This project provides a production-quality local MCP server for Jira Data Center / Server. It runs over STDIO using the official Python MCP SDK (`FastMCP`), connects to Jira through the REST API with `requests`, and is designed to be registered with Codex CLI via `codex mcp add`.

The server exposes two MCP tools:

- `get_issue(key: str)` for a concise structured Jira issue view including the last 5 comments and linked issues
- `search_issues(jql: str, max_results: int)` for JQL-based issue search

## Repository Layout

```text
jira-mcp-starter/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── jira_mcp/
│   ├── __init__.py
│   ├── jira_client.py
│   ├── server.py
│   └── utils.py
└── scripts/
    ├── run.sh
    ├── setup.sh
    └── test_jira_connection.py
```

## Prerequisites

- Python 3.10 or newer
- Access to a Jira Data Center or Jira Server instance
- A Jira username and API token, PAT, or password that your instance accepts for REST authentication
- Shell access to run the setup and launch scripts

## Setup

1. Clone or copy this repository locally.
2. Enter the project directory:

   ```bash
   cd jira-mcp-starter
   ```

3. Run the setup script:

   ```bash
   ./scripts/setup.sh
   ```

4. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

5. Edit `.env` with your Jira settings.

## Environment Variables

The server reads configuration from environment variables or a local `.env` file in the project root.

- `JIRA_BASE_URL`
  Base URL for your Jira instance, for example `https://jira.example.com`
- `JIRA_USER`
  Jira username or service account name
- `JIRA_TOKEN`
  Jira PAT, API token, or password accepted by your Jira deployment
- `JIRA_VERIFY_TLS`
  Optional. Defaults to `true`. Set to `false` only when you must connect to a Jira instance using a self-signed or otherwise untrusted certificate

Example `.env`:

```dotenv
JIRA_BASE_URL=https://jira.example.com
JIRA_USER=svc_codex
JIRA_TOKEN=replace-me
JIRA_VERIFY_TLS=true
```

## Test Jira Connectivity

After `.env` is configured, validate connectivity by fetching a known issue:

```bash
./scripts/test_jira_connection.py ABC-123
```

This script automatically re-execs under `.venv/bin/python` when the virtual environment exists, loads `.env`, calls Jira, and prints the returned issue JSON if the request succeeds.

## Run the MCP Server

Start the local STDIO server with:

```bash
./scripts/run.sh
```

The server logs to `stderr` so MCP protocol messages on `stdout` remain clean.

## Connect to Codex

From the repository root, register the MCP server with Codex using:

```bash
codex mcp add jira \
  --env JIRA_BASE_URL=https://jira.example.com \
  --env JIRA_USER=your.username \
  --env JIRA_TOKEN=your-token \
  --env JIRA_VERIFY_TLS=true \
  -- python jira_mcp/server.py
```

If you prefer to rely on the local `.env` file instead of passing values inline, use:

```bash
codex mcp add jira -- ./scripts/run.sh
```

## Example Codex Prompts

- `Fetch Jira issue ABC-123 and summarize it`
- `Search Jira for open bugs in project ABC`

## Implementation Notes

- Uses `requests` with explicit timeouts and basic retry logic
- Handles authentication errors, missing issues, network failures, invalid JSON, and empty fields
- Supports self-signed certificates through `JIRA_VERIFY_TLS=false`
- Returns concise structured tool output to keep Codex responses readable

## Troubleshooting

- Authentication failures:
  Verify `JIRA_USER` and `JIRA_TOKEN`, and confirm that your Jira instance accepts those credentials for REST API access.
- TLS failures:
  If your Jira server uses a self-signed certificate, set `JIRA_VERIFY_TLS=false` for development or install the correct CA certificate on the machine.
- 404 issue errors:
  Confirm the issue key exists and the configured Jira account has permission to read it.
- Empty search results:
  Verify the JQL is valid and that the Jira account can see matching issues.

## Checklist

- Fill in `.env` with `JIRA_BASE_URL`, `JIRA_USER`, and `JIRA_TOKEN`
- Run `./scripts/setup.sh`
- Test with `./scripts/test_jira_connection.py ABC-123`
- Connect Codex with `codex mcp add jira ... -- python jira_mcp/server.py`
