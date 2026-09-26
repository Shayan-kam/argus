"""
Backward-compatible wrapper for repository source collection.

The actual source collection logic now lives in repository.py.

This file is temporarily retained so older imports do not break.
"""

from repository import (
    get_relevant_files,
    read_file_safely,
    collect_source_code
)