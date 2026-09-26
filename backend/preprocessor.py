"""
Fast repository preprocessing for Argus.

This module does not attempt to prove that a vulnerability exists.

Instead, it identifies signals that indicate which vulnerability
categories may be relevant.

The results are used to decide which expensive LLM agents should run.
"""

import re
from pathlib import Path


# Signals are intentionally broad.
# Their purpose is to identify potentially relevant code, not to make
# final vulnerability decisions.

SIGNAL_PATTERNS = {
    "sql_query": [
        r"\bSELECT\b",
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"\bFROM\b",
        r"\bWHERE\b",
        r"\bJOIN\b",
        r"\bCREATE\s+TABLE\b",
        r"\bDROP\s+TABLE\b"
    ],

    "database_execution": [
        r"cursor\.execute",
        r"\.execute\(",
        r"\.executemany\(",
        r"\.raw\(",
        r"rawquery",
        r"createNativeQuery",
        r"sequelize\.query"
    ],

    "javascript_dom": [
        r"innerHTML",
        r"outerHTML",
        r"insertAdjacentHTML",
        r"document\.write",
        r"eval\("
    ],

    "dangerous_html_rendering": [
        r"dangerouslySetInnerHTML",
        r"Markup\(",
        r"\|safe\b",
        r"mark_safe\(",
        r"v-html"
    ],

    "html_template": [
        r"\{\{.*\}\}",
        r"<%.*%>",
        r"\{%.*%\}",
        r"\.html",
        r"\.jinja",
        r"\.jinja2",
        r"\.hbs",
        r"\.ejs"
    ],

    "user_input": [
        r"request\.",
        r"req\.",
        r"input\(",
        r"query_params",
        r"searchParams",
        r"formData",
        r"request\.GET",
        r"request\.POST",
        r"request\.args"
    ],

    "secret_like_content": [
        r"api[_-]?key",
        r"secret[_-]?key",
        r"access[_-]?token",
        r"auth[_-]?token",
        r"password\s*=",
        r"private[_-]?key",
        r"client[_-]?secret",
        r"aws_access_key_id",
        r"-----BEGIN .* PRIVATE KEY-----"
    ],

    "shell_execution": [
        r"os\.system",
        r"subprocess\.",
        r"child_process",
        r"Runtime\.getRuntime\(\)\.exec",
        r"exec\(",
        r"shell=True"
    ],

    "file_operations": [
        r"open\(",
        r"readFile",
        r"writeFile",
        r"send_file",
        r"FileInputStream"
    ],

    "authentication": [
        r"login",
        r"authenticate",
        r"JWT",
        r"jwt",
        r"session",
        r"password",
        r"authorization",
        r"bearer"
    ],

    # Low-level dynamic memory allocation routines
    "memory_allocation": [
        r"\bmalloc\s*\(",
        r"\bcalloc\s*\(",
        r"\brealloc\s*\(",
        r"\balloca\s*\(",
        r"\bnew\s+[\w\[\]]+",
    ],

    # Memory lifecycle, deallocation, and deletion
    "memory_lifecycle": [
        r"\bfree\s*\(",
        r"\bdelete\s+[\w\[\]]+",
        r"\bdelete\[\]",
    ],

    # Dynamic allocation sizing with arithmetic operations (overflows/wraparounds)
    "alloc_arithmetic": [
        r"\bmalloc\s*\([^)]*[\*\+\-][^)]*\)",
        r"\bcalloc\s*\([^)]*[\*\+\-][^)]*\)",
        r"\brealloc\s*\([^,]+,\s*[^)]*[\*\+\-][^)]*\)",
    ],

    # Filesystem check-then-use conditions vulnerable to TOCTOU races
    "race_conditions": [
        r"\baccess\s*\(",
        r"\bstat\s*\(",
        r"\blstat\s*\(",
        r"\bfstat\s*\(",
    ],

    # String, pointer, and bounded buffer operations
    "buffer_manipulation": [
        r"\bstrcpy\s*\(",
        r"\bstrcat\s*\(",
        r"\bstrncpy\s*\(",
        r"\bstrncat\s*\(",
        r"\bgets\s*\(",
        r"\bsprintf\s*\(",
        r"\bsnprintf\s*\(",
        r"\bvsprintf\s*\(",
        r"\bmemcpy\s*\(",
        r"\bmemmove\s*\(",
        r"\bmemset\s*\(",
        r"\bscanf\s*\("
    ],

    # Low-level permission, identity, and access checks
    "access_control": [
        r"\bsetuid\s*\(",
        r"\bseteuid\s*\(",
        r"\bsetgid\s*\(",
        r"\bsetegid\s*\(",
        r"\bchmod\s*\(",
        r"\bfchmod\s*\(",
        r"\bchown\s*\(",
        r"\bsetgroups\s*\(",
        r"\bcap_set_proc\b"
    ],

    "memory_unsafe": [
        r"\bstrcpy\s*\(",
        r"\bstrcat\s*\(",
        r"\bgets\s*\(",
        r"\bsprintf\s*\(",
        r"\bvsprintf\s*\(",
        r"\bmemcpy\s*\(",
        r"\bmemmove\s*\(",
        r"unsafe\s*\{",
        r"\bmalloc\s*\(",
        r"\bfree\s*\(",
        r"\brealloc\s*\(",
        r"alloca\s*\(",
        r"printf\s*\([^\"]*\+",
        r"scanf\s*\("
    ],

    "native_code": [
        r"#include\s*<",
        r"\bextern\s+\"C\"",
        r"\bJNIEXPORT\b",
        r"\b__asm__\b",
        r"\basm\s*\(",
        r"\.c\"",
        r"\.cpp\"",
        r"\.h\"",
        r"\buintptr_t\b",
        r"\bvoid\s*\*\s*\w+"
    ],

    "binary_format": [
        r"\.elf\b",
        r"\.o\b",
        r"\.so\b",
        r"\.dylib\b",
        r"\.dll\b",
        r"\.bin\b",
        r"\.exe\b",
        r"readObject\s*\(",
        r"ObjectInputStream",
        r"pickle\.loads",
        r"yaml\.load\s*\(",
        r"unserialize\s*\("
    ],

    "unsafe_deserialization": [
        r"pickle\.loads",
        r"pickle\.load",
        r"yaml\.load\s*\(",
        r"ObjectInputStream",
        r"readObject\s*\(",
        r"Marshal\.load",
        r"unserialize\s*\(",
        r"jsonpickle",
        r"dill\.loads",
        r"serde_json::from_str"
    ],

    "assembly_code": [
        r"\bmov\s+",
        r"\bpush\s+",
        r"\bpop\s+",
        r"\bcall\s+",
        r"\bjmp\s+",
        r"\bret\b",
        r"\.section\s+",
        r"\.globl\s+"
    ],

    # CI/CD Workflow & Pipeline Security Signals
    "workflow_injection": [
        r"\$\{\{\s*github\.event\.(issue|pull_request|comment|head_commit|review)",
        r"\$\{\{\s*github\.head_ref\s*\}\}",
        r"\$\{\{\s*inputs\.",
    ],

    "ci_pipeline": [
        r"\bpull_request_target\b",
        r"permissions:\s*write-all",
        r"actions/checkout@",
        r"\.github/workflows",
        r"gitlab-ci\.yml",
    ],

    "container_misconfig": [
        r"/var/run/docker\.sock",
        r"privileged:\s*true",
        r"network_mode:\s*[\"']?host[\"']?",
        r"cap_add:\s*.*SYS_ADMIN",
    ],

    "privileged_execution": [
        r"^\s*USER\s+root\b",
        r"\bsudo\s+[\w\-]+",
        r"--privileged",
    ],

    "insecure_action": [
        r"uses:\s*[\w\-_]+/[\w\-_]+@(master|main|v[0-9]+(\.[0-9]+)*)\b",
    ],
}


def detect_languages(source_files):
    """
    Identify languages based on file extensions and manifest filenames.
    """

    languages = set()

    for source_file in source_files:
        file_path = Path(source_file["file"])
        filename = file_path.name.lower()
        extension = file_path.suffix.lower()

        extension_to_language = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".php": "php",
            ".rb": "ruby",
            ".go": "go",
            ".cs": "csharp",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".c": "c",
            ".rs": "rust",
            ".asm": "assembly",
            ".s": "assembly",
            ".sql": "sql",
            ".yml": "yaml",
            ".yaml": "yaml",
        }

        if extension in extension_to_language:
            languages.add(extension_to_language[extension])
        elif "dockerfile" in filename:
            languages.add("dockerfile")

    return sorted(languages)


def find_signals_in_file(file_path, content):
    """
    Return all detected signals for one file.

    Each signal includes the line numbers where it appeared.
    """

    detected_signals = {}

    lines = content.splitlines()

    for signal_name, patterns in SIGNAL_PATTERNS.items():
        matching_lines = []

        for line_number, line in enumerate(lines, start=1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    matching_lines.append({
                        "line": line_number,
                        "content": line.strip()[:500]
                    })
                    break

        if matching_lines:
            detected_signals[signal_name] = matching_lines

    return detected_signals


def preprocess_repository(source_files):
    """
    Analyze all collected source files.

    Returns a repository analysis object used by the routing system.
    """

    repository_signals = {}
    file_signals = {}
    total_signal_count = 0

    for source_file in source_files:
        file_path = source_file["file"]
        content = source_file["content"]

        signals = find_signals_in_file(file_path, content)

        if signals:
            file_signals[file_path] = signals

        for signal_name, matches in signals.items():
            total_signal_count += len(matches)

            if signal_name not in repository_signals:
                repository_signals[signal_name] = []

            repository_signals[signal_name].append({
                "file": file_path,
                "matches": matches
            })

    return {
        "languages": detect_languages(source_files),
        "signals": repository_signals,
        "file_signals": file_signals,
        "total_signal_count": total_signal_count
    }