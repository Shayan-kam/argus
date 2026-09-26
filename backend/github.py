"""
GitHub repository cloning utilities.
"""

import re
import subprocess
import tempfile
from pathlib import Path


GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/[^/]+/[^/]+/?$"
)


def clone_repository(repository_url, destination_directory=None):
    """
    Clones a public GitHub repository.

    Returns:
        Path to the cloned repository.
    """

    repository_url = repository_url.rstrip("/")

    if not GITHUB_URL_PATTERN.match(repository_url):

        raise ValueError("Please provide a valid public GitHub repository URL.")

    if destination_directory is not None:
        target_directory = Path(destination_directory)
        target_directory.mkdir(parents=True, exist_ok=True)
    else:
        target_directory = Path(tempfile.mkdtemp(prefix="argus-repository-"))

    repository_path = target_directory / "repository"

    result = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            repository_url,
            str(repository_path)
        ],
        capture_output=True,
        text=True,
        timeout=120
    )

    if result.returncode != 0:

        raise RuntimeError(f"Git clone failed: {result.stderr}")

    return str(repository_path)