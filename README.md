# Argus

Argus is a local web application for reviewing public GitHub repositories for potential source-code security issues. A FastAPI backend clones and scans the repository, combines deterministic rules with signal-routed Google Gemini agents, streams scan progress to a React frontend, and creates a downloadable PDF report.

Argus is a triage aid, not a replacement for a security review, a full static-analysis suite, or a penetration test. Its rules and AI findings can be incomplete or incorrect; verify findings against the code and the application's runtime behavior.

## Contents

- [Features](#features)
- [How a scan works](#how-a-scan-works)
- [Security agents](#security-agents)
- [Requirements](#requirements)
- [Setup](#setup)
- [Configuration](#configuration)
- [Run Argus](#run-argus)
- [HTTP API](#http-api)
- [Source collection and limits](#source-collection-and-limits)
- [Privacy and security](#privacy-and-security)
- [Validation](#validation)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)

## Features

- Scans GitHub repositories using a URL, including pasted repository subpage URLs.
- Supports public repositories and private repositories using a GitHub personal access token.
- Provides three scan profile choices and live server-sent progress updates.
- Runs deterministic checks before selecting relevant Gemini agents based on detected code signals.
- Supports multiple Gemini API keys and assigns agents to key slots in round-robin order, with key failover for authentication and quota errors.
- Displays routing, preprocessing signals, agent results, finding severity, repository summary, and timing in the frontend.
- Generates a PDF report for each completed scan.

## How a scan works

1. The API normalizes the supplied GitHub URL and shallow-clones the repository into a temporary directory.
2. The collector reads supported source and configuration files, skipping common dependency and build directories.
3. The preprocessor detects broad signals such as SQL operations, request data, unsafe HTML rendering, credentials, native code, and deserialization.
4. Deterministic rules inspect the collected files and create rule-based findings.
5. In `standard` and `deep` profiles, the router selects agents for which relevant signals were found. Each selected agent receives the files associated with its signal categories.
6. Selected agents run concurrently up to the configured worker limit. The results are merged and deduplicated.
7. Argus summarizes repository metadata, writes a PDF report, and streams the completed scan result to the frontend.
8. The temporary clone is removed after the scan. The generated PDF remains in the backend reports directory for the server session.

The current implementation treats `standard` and `deep` the same: both run deterministic rules and signal-routed Gemini agents. They do not yet perform separate analysis passes. `quick` runs deterministic rules only and does not call Gemini.

## Security agents

| Agent | Focus | Routing signals |
| --- | --- | --- |
| SQL Injection Agent | Dynamic SQL construction and unsafe database queries | `sql_query`, `database_execution`, optionally `user_input` |
| Cross-Site Scripting Agent | Unsafe browser HTML rendering and templates | `javascript_dom`, `dangerous_html_rendering`, `html_template`, optionally `user_input` |
| Hardcoded Secrets Agent | Credentials or keys embedded in source/configuration | `secret_like_content` |
| Binary Exploitation Agent | Native and memory-unsafe code patterns | `memory_unsafe`, `native_code`, optionally `shell_execution` or `assembly_code` |
| Reverse Engineering Agent | Binary formats and unsafe deserialization patterns | `unsafe_deserialization`, `binary_format`, optionally `native_code` or `authentication` |

The preprocessor is deliberately heuristic: a signal is a reason to route a review, not proof that a vulnerability exists. The deterministic rules currently cover patterns associated with SQL injection, unsafe HTML/XSS, command and code injection, path traversal, server-side request forgery, open redirects, hardcoded credentials, weak cryptography, disabled TLS verification, debug mode, and permissive CORS.

## Requirements

- Python 3.10 or later is recommended.
- Node.js and npm compatible with the installed Vite 7 release.
- Git available on `PATH` for cloning repositories.
- A Google Gemini API key for `standard` and `deep` scans. Quick scans do not require one.
- Network access to GitHub; Gemini access is also required for selected AI agents.

## Setup

Run the backend and frontend in separate terminals from the repository root.

### Backend

Create and activate a virtual environment, then install the backend dependencies:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r ../requirements.txt
```

On macOS or Linux, activate the environment with `source .venv/bin/activate` instead.

Create `backend/.env` using the configuration example below. Do not commit this file.

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
```

The frontend uses `http://localhost:8000` for the backend by default. To use another backend origin, create `frontend/.env.local` and set:

```dotenv
VITE_API_URL=http://localhost:8000
```

Restart Vite after changing frontend environment variables.

## Configuration

Create `backend/.env` with the settings you need:

```dotenv
# Required for standard and deep scans
GEMINI_API_KEY=your-first-gemini-api-key
GEMINI_MODEL=gemini-3.8-flash

# Optional additional Gemini keys. Number each key and its optional model.
GEMINI_API_KEY2=your-second-gemini-api-key
GEMINI_MODEL2=gemini-3.8-flash
GEMINI_API_KEY3=your-third-gemini-api-key
GEMINI_MODEL3=gemini-3.8-flash

# Optional retry and concurrency settings
GEMINI_MAX_RETRIES=4
GEMINI_RETRY_BASE_DELAY=2
GEMINI_MAX_CONCURRENT_AGENTS=2

# Optional: access private GitHub repositories without sending a token per request
GITHUB_TOKEN=your-github-personal-access-token
```

Only non-empty `GEMINI_API_KEY`, `GEMINI_API_KEY2`, `GEMINI_API_KEY3`, and subsequent numbered variables are used. Duplicate key values count as one key slot. A numbered `GEMINI_MODEL<N>` applies to the matching numbered key; otherwise the global `GEMINI_MODEL` is used. If no `GEMINI_API_KEY` variable is set, `GOOGLE_API_KEY` can be used as a single-key fallback.

### Gemini key assignment

Selected agents are assigned to configured Gemini key slots in round-robin order. For example, with two configured keys, three selected agents start on slots `1`, `2`, and `1`. If a request receives an authentication or quota response, Argus tries another configured key. The backend logs the assigned slot; it never needs to log the key value.

Multiple keys only provide independent quota when Google treats them as belonging to projects with independent quota. Multiple keys created in the same Google Cloud project generally share project quota. Adding more key variables does not bypass project-level limits.

`GEMINI_MAX_CONCURRENT_AGENTS` is a cap on simultaneous agent requests, not a key selector:

| Value | Behavior |
| --- | --- |
| `1` | Run one selected agent request at a time. |
| `2` | Allow up to two agent requests at once. |
| Unset | Default to one worker per configured Gemini key, with a minimum of one worker. |

The legacy `GEMINI_MAX_CONCURRENT` variable takes precedence if set. Increasing concurrency can reduce scan time when multiple agents are selected, but can also hit rate limits sooner. `GROQ_API_KEY` is not used by the Gemini integration; Groq requires a separate provider client and routing implementation.

## Run Argus

Start the backend from the `backend` directory:

```powershell
cd backend
\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend from `frontend` in the second terminal:

```powershell
cd frontend
npm run dev
```

Open the Vite URL printed in the frontend terminal, normally `http://localhost:5173`. The backend API and interactive OpenAPI documentation are available at `http://localhost:8000` and `http://localhost:8000/docs` respectively. The backend CORS configuration allows localhost and 127.0.0.1 origins.

To create a frontend production bundle, run `npm exec -- vite build` from `frontend`. The current `package.json` maps `npm run build` to `vite`, which starts the development server rather than performing a production build.

## HTTP API

Interactive request and response schemas are available at `/docs` while the backend is running.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Service name, status, and version. |
| `GET` | `/api/health` | Health check. |
| `GET` | `/api/agents` | Registered agents and their routing signals. |
| `GET` | `/api/capabilities` | Scan profiles, repository access options, provider, and agent count. |
| `POST` | `/api/analyze` | Start a scan and receive server-sent events. |
| `GET` | `/api/report/{scan_id}` | Download the completed scan's PDF report. |

### Start a scan

`POST /api/analyze` accepts JSON:

```json
{
    "repository_url": "https://github.com/owner/repository",
    "scan_profile": "standard",
    "github_token": "optional-token-for-a-private-repository"
}
```

`repository_url` is required. `scan_profile` defaults to `standard` and must be `quick`, `standard`, or `deep`. `github_token` is optional; if omitted, the backend checks `GITHUB_TOKEN` in its environment. A GitHub personal access token needs access to the private repository (the classic token requires the `repo` scope).

The endpoint streams `text/event-stream`. Each event is a JSON object preceded by `data:` and separated by a blank line. Progress events have `type: "progress"`; a successful scan ends with a `type: "complete"` event whose `result` contains the scan response. Failures are sent as `type: "error"` events with a `detail` string.

Example request:

```bash
curl -N http://localhost:8000/api/analyze \
    -H "Content-Type: application/json" \
    -d '{"repository_url":"https://github.com/owner/repository","scan_profile":"quick"}'
```

The completed result includes a scan ID, normalized repository URL, repository overview, collected-file count, findings, severity totals, rule and AI finding counts, selected and skipped agents, preprocessing languages/signals, per-agent results, timing data, and a `report_url`.

Finding objects include an ID, title, vulnerability type, severity, confidence, file path, optional line number, evidence, description, recommendation, and source (`rule-based`, `ai`, or `hybrid`). The PDF report is available at the returned `report_url` or `/api/report/{scan_id}`.

## Source collection and limits

The collector currently recognizes Python, JavaScript/TypeScript, Java, PHP, Ruby, Go, C/C++, C#, Rust, SQL, HTML, Vue, environment files, and common configuration formats such as JSON, YAML, XML, INI, TOML, properties, and `.conf` files. It skips `.git`, `node_modules`, virtual environments, Python caches, build output, `.next`, and coverage directories. Common JavaScript lock files are excluded.

At most 150 files are collected per scan. Each file is truncated after 80,000 characters. A repository can contain additional files that are not reviewed because of these limits or unsupported file types.

## Privacy and security

- Repository cloning and deterministic scanning run in the backend process. For `standard` and `deep`, source from files selected for an agent is sent to Google Gemini to produce an analysis. Review Google's applicable API data-handling terms before scanning confidential code.
- The collector recognizes `.env` and configuration files. Do not assume credentials in a repository are automatically removed before an AI request. Avoid scanning live secrets; use test credentials and rotate any credential exposed in source control.
- Quick scans do not send source to Gemini, but they still clone the GitHub repository and may query GitHub metadata for the repository overview.
- Private-repository GitHub tokens are used for cloning and metadata access and are not saved in scan results. Prefer the request-body token for one-off scans; do not put tokens in URLs or commit them.
- Keep Gemini and GitHub credentials in ignored local environment files or a secret manager. Never commit `.env` files.
- Cloned source is deleted after each scan. PDFs are stored under `backend/reports` when the server is started from `backend`; clean that directory when reports are no longer needed.
- Argus runs without user authentication. Keep the backend bound to localhost unless you add appropriate authentication, authorization, and deployment protections.

## Validation

Compile the Python backend modules from `backend`:

```powershell
cd backend
python -m compileall -q .
```

Build the frontend from `frontend`:

```powershell
cd frontend
npm exec -- vite build
```

The project currently has no configured automated test suite. Use `/api/health`, `/api/agents`, and a small public test repository to smoke-test a local setup. A quick scan is useful for checking the clone, progress stream, deterministic rules, result display, and PDF workflow without requiring Gemini quota.

## Project layout

```text
Argus/
|-- requirements.txt     Backend Python dependencies
|-- backend/
|   |-- agents/          Specialized Gemini security agents
|   |-- reports/         Generated PDF reports
|   |-- main.py          FastAPI routes and SSE scan lifecycle
|   |-- orchestrator.py  Scan pipeline, progress, and agent scheduling
|   |-- gemini_base.py   Gemini key pool, retries, and failover
|   |-- preprocessor.py  Language and security-signal detection
|   |-- routing.py       Agent and focused-file selection
|   |-- rules.py         Deterministic vulnerability checks
|   |-- repository.py    Source-file discovery and reading limits
|   |-- github.py        GitHub URL handling, cloning, and overview
|   |-- findings.py      Finding schema, normalization, deduplication
|   |-- report.py        PDF report generation
`-- frontend/
        |-- src/
        |   |-- components/  Scan form, progress, findings, and summaries
        |   |-- App.jsx      Scan workflow and SSE client
        |   `-- App.css      Application styles
        |-- index.html
        `-- package.json    Vite scripts and React dependencies
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Frontend cannot connect to the API | Confirm Uvicorn is running on port 8000. Set `VITE_API_URL` if the API uses another origin, then restart Vite. |
| Private repository clone fails | Confirm the repository URL and provide a GitHub token with access to that repository. |
| No Gemini agents are selected | The router runs only agents matching detected signals. Try a repository containing code relevant to one of the agent trigger categories; `quick` never runs agents. |
| Gemini returns `401` or `403` | Check that each configured Gemini key is valid and enabled for the Gemini API. Argus can try another configured Gemini key. |
| Gemini returns `429` or `RESOURCE_EXHAUSTED` | The key or Google project has reached a rate or quota limit. Wait for quota recovery, reduce concurrency, or configure a key with independently available quota. |
| Scan completes with agent failures | Inspect the agent results panel and backend log for the error. A scan with failed agents is incomplete even if it has zero findings. |
| PDF download returns 404 | Reports are local to the backend process and are created only after a scan completes. Use the `report_url` from that scan result. |
