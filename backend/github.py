"""
GitHub repository cloning utilities.

Supports public repositories and private repositories when a
GitHub personal access token (PAT) is supplied via the request
body or the GITHUB_TOKEN environment variable.

Private repo access requires a token with the `repo` scope.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
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
