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

   Or use the Makefile convenience target:

   ```bash
   make setup
   ```

4. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

5. Edit `.env` with your Jira settings.

## Using Make

The repository includes an optional `Makefile` as a convenience layer over the existing scripts. It does not replace the scripts or Python tooling; it simply gives you shorter, stable commands for common workflows.

Common commands:

```bash
make
make setup
make test
make run
make test-live
make connection-test ISSUE=ABC-123
make clean
```

`make` by itself prints the available targets.

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
- `REQUESTS_CA_BUNDLE`
  Optional. Path to a PEM CA bundle file for this project. Use this when you want Python `requests` to trust your internal CA without disabling TLS verification for Jira requests

Example `.env`:

```dotenv
JIRA_BASE_URL=https://jira.example.com
JIRA_USER=svc_codex
JIRA_TOKEN=replace-me
JIRA_VERIFY_TLS=true
# REQUESTS_CA_BUNDLE=/absolute/path/to/corporate-root-ca.pem
JIRA_TEST_ISSUE_KEY=ABC-123
JIRA_TEST_JQL=project = ABC ORDER BY updated DESC
```

Optional test-only variables:

- `JIRA_TEST_ISSUE_KEY`
  A real Jira issue key used by the live integration test
- `JIRA_TEST_JQL`
  Optional JQL for the live search test. Defaults to `project = ABC ORDER BY updated DESC` in the example template and falls back to `issuekey = <JIRA_TEST_ISSUE_KEY>` if omitted

## Test Jira Connectivity

After `.env` is configured, validate connectivity by fetching a known issue:

```bash
./scripts/test_jira_connection.py ABC-123
```

Or:

```bash
make connection-test ISSUE=ABC-123
```

This script automatically re-execs under `.venv/bin/python` when the virtual environment exists, loads `.env`, calls Jira, and prints the returned issue JSON if the request succeeds.

## Run the MCP Server

Start the local STDIO server with:

```bash
./scripts/run.sh
```

Or:

```bash
make run
```

The server logs to `stderr` so MCP protocol messages on `stdout` remain clean.

## Trust an Internal CA Certificate

If your Jira Data Center or Jira Server instance uses a certificate chain signed by an internal or self-managed CA, prefer adding that CA certificate to the operating system trust store or setting `REQUESTS_CA_BUNDLE`. Avoid setting `JIRA_VERIFY_TLS=false` unless you are doing short-lived local debugging.

### Windows

For a machine-wide trust configuration:

1. Export the root CA certificate from your internal PKI as a public `.cer` file.
2. Open the local machine certificate manager with `certlm.msc` or use `mmc` with the Certificates snap-in for the local computer.
3. Import the certificate into `Trusted Root Certification Authorities`.

Command-line alternative:

```powershell
certutil -addstore root C:\path\to\corporate-root.cer
```

After import, start a new shell before rerunning the connection test.

### macOS

Using Keychain Access:

1. Open `Keychain Access`.
2. Select the `System` keychain.
3. Drag the CA certificate into Keychain Access.
4. Open the certificate, expand `Trust`, and set the relevant SSL trust policy if your environment requires an explicit override.

Restart the terminal session after import so tools pick up the updated trust settings.

### Linux

Linux trust-store commands vary by distribution.

For Debian or Ubuntu:

```bash
sudo cp corporate-root-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

For RHEL, Rocky, AlmaLinux, CentOS Stream, or Fedora:

```bash
sudo cp corporate-root-ca.crt /etc/pki/ca-trust/source/anchors/
sudo update-ca-trust extract
```

If browser-based testing still fails after installing the CA, restart the browser. On Ubuntu, snap-packaged applications may not automatically pick up certificates added to the host trust store.

### Project-Local Alternative

If you do not want to change the operating system trust store, point Python `requests` at a CA bundle file:

```dotenv
REQUESTS_CA_BUNDLE=/absolute/path/to/corporate-root-ca.pem
```

This keeps `JIRA_VERIFY_TLS=true` while allowing this project to trust your internal CA.

## Run Automated Tests

Run the complete local test suite with:

```bash
./scripts/run_tests.sh
```

Or:

```bash
make test
```

This runs:

- mocked unit tests that do not require Jira access
- mocked server tool tests that validate the MCP-facing output shape
- optional live integration tests that run only when `JIRA_TEST_ISSUE_KEY` is set in `.env` or your shell

To run only unit tests:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

To run only the live Jira validation tests after configuration:

```bash
python -m unittest tests.test_live_jira -v
```

Or:

```bash
make test-live
```

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
- Set `JIRA_TEST_ISSUE_KEY` to a real issue for live validation
- Run `./scripts/setup.sh`
- Test with `./scripts/test_jira_connection.py ABC-123`
- Run `./scripts/run_tests.sh`
- Connect Codex with `codex mcp add jira ... -- python jira_mcp/server.py`
