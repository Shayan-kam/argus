"""
Repository source-code collection utilities.

Responsibilities:

1. Discover relevant source files.
2. Ignore dependency and build directories.
3. Read source files safely.
4. Limit the amount of source code sent to specialized agents.
"""

from pathlib import Path


# File types that Argus currently analyzes.
SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".php",
    ".rb",
    ".go",
    ".cs",
    ".cpp",
    ".c",
    ".sql",
    ".html",
    ".htm",
    ".vue",
    ".env",
    ".yml",
    ".yaml",
    ".json",
    ".xml",
    ".ini",
    ".toml",
    ".properties",
    ".conf"
}


IGNORED_FILE_NAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml"
}


# Directories that should not be analyzed.
IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "coverage"
}


def get_relevant_files(repository_path):
    """
    Finds source files that may contain security vulnerabilities.

    Args:
        repository_path: Path to the cloned repository.

    Returns:
        A list of source file paths.
    """

    repository_path = Path(repository_path)

    relevant_files = []

    for path in repository_path.rglob("*"):

        if not path.is_file():
            continue

        # Skip ignored directories.
        if any(
            ignored_directory in path.parts
            for ignored_directory in IGNORED_DIRECTORIES
        ):
            continue

        if path.name in IGNORED_FILE_NAMES:
            continue

        # Only include supported source-code extensions.
        # Dotfiles such as .env have an empty suffix, so the name is checked too.
        if (
            path.suffix.lower() not in SOURCE_EXTENSIONS
            and path.name not in {".env", ".env.local"}
        ):
            continue

        relevant_files.append(path)

    return relevant_files


def read_file_safely(file_path, repository_path):
    """
    Reads a source file while preventing extremely large prompts.

    Args:
        file_path: Absolute path to the source file.
        repository_path: Root path of the repository.

    Returns:
        A dictionary containing the relative path and content.
        Returns None if the file cannot be read.
    """

    try:

        content = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    except Exception as error:

        print(f"Could not read {file_path}: {error}")

        return None

    # Keep enough of each file for a detailed review.
    max_characters = 80000

    if len(content) > max_characters:

        content = content[:max_characters]
        content += "\n\n[File truncated]"

    relative_path = file_path.relative_to(repository_path)

    return {
        "file": str(relative_path),
        "content": content
    }


def collect_source_code(repository_path):
    """
    Collects source code from the repository.

    This is intentionally limited for the MVP.
    Later, this can be replaced with intelligent batching.
    """

    repository_path = Path(repository_path)

    files = get_relevant_files(repository_path)

    max_files = 150
    files = sorted(files)[:max_files]

    source_files = []

    for file_path in files:

        source_file = read_file_safely(
            file_path,
            repository_path
        )

        if source_file:
            source_files.append(source_file)

    return source_files