# Argus

AI-powered source code security scanner for GitHub repositories.

## Architecture

```
Repository
    ↓
Preprocessor (signal detection)
    ↓
Agent Router (select relevant agents)
    ↓
Gemini Agents (SQLi, XSS, Secrets, Pwn, Rev)
    ↓
Findings + PDF Report
```

## Agents

| Agent | Category | Triggers |
|-------|----------|----------|
| SQL Injection | web | sql_query, database_execution |
| Cross-Site Scripting | web | javascript_dom, html_template |
| Hardcoded Secrets | secrets | secret_like_content |
| Binary Exploitation | pwn | memory_unsafe, native_code |
| Reverse Engineering | rev | unsafe_deserialization, binary_format |

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:

```
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash

# Optional — for private repos without passing token in API requests
GITHUB_TOKEN=ghp_...
```

Run:

```bash
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Private Repositories

Private GitHub repos are supported via a personal access token with the **`repo`** scope.

**Option 1 — API request:** Pass `github_token` in the analyze request body.

**Option 2 — Environment variable:** Set `GITHUB_TOKEN` in `backend/.env`.

The token is used only during `git clone` and is not stored.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/agents` | List available agents |
| GET | `/api/capabilities` | Scan profiles and access options |
| POST | `/api/analyze` | Clone and analyze a repository |
| GET | `/api/report/{scan_id}` | Download PDF report |

### Analyze request

```json
{
  "repository_url": "https://github.com/owner/repo",
  "scan_profile": "standard",
  "github_token": "optional-for-private-repos"
}
```

Scan profiles: `quick` (rules only), `standard`, `deep`.
