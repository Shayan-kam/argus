"""
GitHub repository cloning utilities.

Supports public repositories and private repositories when a
GitHub personal access token (PAT) is supplied via the request
body or the GITHUB_TOKEN environment variable.

Private repo access requires a token with the `repo` scope.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse


GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/[^/]+/[^/]+/?$"
)


def normalize_github_url(repository_url):
    """
    Keep only https://github.com/owner/repo.

    Extra path segments such as /branches, /tree/main, or /blob/...
    are removed so a pasted GitHub page still clones the repository.
    """

    parsed = urlparse(repository_url.strip())
    parts = [
        part for part in parsed.path.split("/")
        if part
    ]

    if len(parts) < 2:
        return repository_url.strip().rstrip("/")

    owner = parts[0]
    repository = parts[1]

    if repository.endswith(".git"):
        repository = repository[:-4]

    host = parsed.netloc or "github.com"
    scheme = parsed.scheme or "https"

    return f"{scheme}://{host}/{owner}/{repository}"


def build_authenticated_url(repository_url, github_token=None):
    """
    Inject a GitHub token into an HTTPS clone URL when provided.

    Token priority:
    1. Explicit token passed to the function.
    2. GITHUB_TOKEN environment variable.
    """

    token = github_token or os.getenv("GITHUB_TOKEN")

    if not token:
        return repository_url

    parsed = urlparse(repository_url)

    if parsed.scheme not in ("http", "https"):
        return repository_url

    host = parsed.netloc or "github.com"
    path = parsed.path or ""

    return f"https://{token}@{host}{path}"


def clone_repository(
    repository_url,
    destination_directory=None,
    github_token=None
):
    """
    Clone a GitHub repository.

    Public repos clone without authentication. Private repos require
    a personal access token with the `repo` scope, supplied either
    through the github_token argument or the GITHUB_TOKEN env var.

    Returns:
        Path to the cloned repository.
    """

    repository_url = normalize_github_url(repository_url)

    if not GITHUB_URL_PATTERN.match(repository_url):
        raise ValueError(
            "Please provide a valid GitHub repository URL "
            "(https://github.com/owner/repo)."
        )

    if destination_directory is not None:
        target_directory = Path(destination_directory)
        target_directory.mkdir(parents=True, exist_ok=True)
    else:
        target_directory = Path(
            tempfile.mkdtemp(prefix="argus-repository-")
        )

    repository_path = target_directory / "repository"
    clone_url = build_authenticated_url(
        repository_url,
        github_token
    )

    env = os.environ.copy()

    # Prevent git from prompting interactively when no token is set.
    env["GIT_TERMINAL_PROMPT"] = "0"

    result = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            clone_url,
            str(repository_path)
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=env
    )

    if result.returncode != 0:
        stderr = result.stderr or ""

        if "Authentication failed" in stderr or "could not read Username" in stderr:
            raise RuntimeError(
                "Git clone failed: authentication required. "
                "Provide a GitHub personal access token with the "
                "`repo` scope for private repositories."
            )

        if "Repository not found" in stderr:
            raise RuntimeError(
                "Git clone failed: repository not found. "
                "Verify the URL and that your token has access."
            )

        raise RuntimeError(f"Git clone failed: {stderr}")

    return str(repository_path)


README_NAMES = (
    "README.md",
    "README.markdown",
    "README.rst",
    "README.txt",
    "README"
)


def _repository_name(repository_url):
    parts = [
        part for part in urlparse(repository_url).path.split("/")
        if part
    ]

    if len(parts) < 2:
        return "This repository"

    return parts[1]


def _fetch_github_description(repository_url, github_token=None):
    """
    Read the short description GitHub stores for the repository.
    """

    parts = [
        part for part in urlparse(repository_url).path.split("/")
        if part
    ]

    if len(parts) < 2:
        return ""

    request = Request(
        f"https://api.github.com/repos/{parts[0]}/{parts[1]}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Argus"
        }
    )
    token = github_token or os.getenv("GITHUB_TOKEN")

    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        return ""

    description = payload.get("description") or ""

    return re.sub(r"\s+", " ", description).strip()


def _readme_text(repository_path):
    root = Path(repository_path)

    for name in README_NAMES:
        candidate = root / name

        if candidate.is_file():
            return candidate.read_text(
                encoding="utf-8",
                errors="ignore"
            )[:12000]

    return ""


def _readme_paragraphs(readme):
    text = re.sub(r"<!--.*?-->", " ", readme, flags=re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    paragraphs = []
    current = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue

        if (
            line.startswith("![")
            or line.startswith("[![")
            or line.startswith("<img")
            or line.startswith("|")
            or set(line) <= {"-", "=", " ", ":"}
        ):
            continue

        if line.startswith("#"):
            line = line.lstrip("#").strip()

        line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"[*_>#]", "", line)
        line = re.sub(r"\s+", " ", line).strip()

        if line:
            current.append(line)

    if current:
        paragraphs.append(" ".join(current))

    return [
        paragraph for paragraph in paragraphs
        if len(paragraph) > 50
    ]


def _package_description(repository_path):
    package_path = Path(repository_path) / "package.json"

    if not package_path.is_file():
        return ""

    try:
        payload = json.loads(
            package_path.read_text(encoding="utf-8", errors="ignore")
        )
    except json.JSONDecodeError:
        return ""

    description = payload.get("description") or ""

    return re.sub(r"\s+", " ", str(description)).strip()


def _trim_summary(text):
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) <= 420:
        return text

    shortened = text[:420].rsplit(" ", 1)[0].rstrip(".,;:")

    if "." in shortened:
        shortened = shortened.rsplit(".", 1)[0] + "."

    return shortened


LANGUAGE_NAMES = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "java": "Java",
    "php": "PHP",
    "ruby": "Ruby",
    "go": "Go",
    "csharp": "C#",
    "cpp": "C++",
    "c": "C",
    "rust": "Rust",
    "assembly": "assembly",
    "sql": "SQL"
}

ROLE_HINTS = (
    (("auth", "login", "session", "password"), "authentication"),
    (("database", "db", "model", "query"), "database access"),
    (("template", "html", "view", "page"), "web pages"),
    (("admin",), "administration"),
    (("api", "route", "controller", "endpoint"), "request handling"),
    (("report",), "reporting"),
    (("challenge",), "security challenges"),
    (("config", "setting"), "configuration"),
    (("secret", "credential", "token"), "stored credentials"),
    (("test", "spec"), "tests")
)


def _display_languages(languages):
    return [
        LANGUAGE_NAMES.get(language, language)
        for language in languages
    ]


def _join_phrases(phrases):
    phrases = list(phrases)

    if not phrases:
        return ""

    if len(phrases) == 1:
        return phrases[0]

    return f"{', '.join(phrases[:-1])} and {phrases[-1]}"


def _code_activity_summary(repository_path, languages):
    """
    Describe the code from file names when the repository has little written about it.
    """

    root = Path(repository_path)
    found_roles = set()
    skipped = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    inspected = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if skipped.intersection(path.parts):
            continue

        inspected += 1

        if inspected > 400:
            break

        blob = f"{path.parent.name} {path.stem}".lower()

        for keys, label in ROLE_HINTS:
            if any(key in blob for key in keys):
                found_roles.add(label)

    sentences = []
    shown_roles = [
        label for _, label in ROLE_HINTS
        if label in found_roles and label != "tests"
    ][:4]

    if shown_roles:
        sentences.append(
            f"The code includes {_join_phrases(shown_roles)}."
        )

    shown_languages = _display_languages(languages or [])

    if shown_languages:
        sentences.append(
            f"It is written in {_join_phrases(shown_languages)}."
        )

    return " ".join(sentences)


def _fallback_summary(repository_url, languages):
    name = _repository_name(repository_url)

    if languages:
        listed = ", ".join(languages)
        return (
            f"{name} is written in {listed}. "
            "The scan reviewed the source in this repository."
        )

    return (
        f"{name} is a source code repository. "
        "The scan reviewed the files that were available to analyze."
    )


def summarize_repository(
    repository_path,
    repository_url,
    languages=None,
    github_token=None
):
    """
    Build a short description of what the repository is and what its code does.
    """

    paragraphs = _readme_paragraphs(_readme_text(repository_path))
    readme_summary = " ".join(paragraphs[:2]) if paragraphs else ""
    github_description = _fetch_github_description(
        repository_url,
        github_token
    )
    package_description = _package_description(repository_path)
    pieces = []

    for piece in (github_description, package_description, readme_summary):
        if not piece:
            continue

        if any(piece.lower() in existing.lower() for existing in pieces):
            continue

        if any(existing.lower() in piece.lower() for existing in pieces):
            continue

        pieces.append(piece)

    sentences = []

    for piece in pieces:
        if piece[-1] not in ".!?":
            piece += "."

        sentences.append(piece[0].upper() + piece[1:])

    summary = _trim_summary(" ".join(sentences))
    code_summary = _code_activity_summary(
        repository_path,
        languages or []
    )

    if code_summary and code_summary.lower() not in summary.lower():
        if len(summary) < 180:
            summary = _trim_summary(
                f"{summary} {code_summary}".strip()
            )

    if not summary:
        summary = _fallback_summary(repository_url, languages or [])

    return {
        "summary": summary,
        "languages": list(languages or [])
    }
