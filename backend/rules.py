"""
Deterministic vulnerability rules.

Rules execute before LLM agents because they are fast
and can provide evidence for routing and reporting.
"""

import re

from findings import SecurityFinding


def create_rule_finding(
    title,
    vulnerability_type,
    severity,
    confidence,
    file_path,
    line_number,
    evidence,
    description,
    recommendation
):
    return SecurityFinding(
        title=title,
        vulnerability_type=vulnerability_type,
        severity=severity,
        confidence=confidence,
        file=file_path,
        line=line_number,
        evidence=evidence,
        description=description,
        recommendation=recommendation,
        source="rule-based"
    )


def scan_sql_injection_rules(source_files):
    findings = []

    sql_keywords = (
        r"(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|"
        r"JOIN|VALUES|CREATE|DROP|ALTER)"
    )

    for source_file in source_files:
        file_path = source_file["file"]
        content = source_file["content"]
        lines = content.splitlines()

        for line_number, line in enumerate(lines, start=1):
            stripped_line = line.strip()

            if not re.search(
                sql_keywords,
                stripped_line,
                re.IGNORECASE
            ):
                continue

            has_string_concatenation = (
                "+" in stripped_line
                or "f\"" in stripped_line
                or "f'" in stripped_line
                or "${" in stripped_line
                or ".format(" in stripped_line
                or "% " in stripped_line
            )

            has_database_execution = any(
                keyword in stripped_line.lower()
                for keyword in [
                    "execute(",
                    "executemany(",
                    "raw(",
                    "rawquery",
                    "cursor.execute"
                ]
            )

            if not has_string_concatenation:
                continue

            if (
                not has_database_execution
                and "=" not in stripped_line
            ):
                continue

            has_user_input = any(
                keyword in content.lower()
                for keyword in [
                    "request.",
                    "request[",
                    "request.args",
                    "request.form",
                    "request.json",
                    "input(",
                    "query_params",
                    "argv"
                ]
            )

            severity = "High" if has_user_input else "Medium"
            confidence = 0.88 if has_user_input else 0.72

            evidence = stripped_line[:500]

            findings.append(
                create_rule_finding(
                    title="Potential SQL Injection",
                    vulnerability_type="SQL Injection",
                    severity=severity,
                    confidence=confidence,
                    file_path=file_path,
                    line_number=line_number,
                    evidence=evidence,
                    description=(
                        "The code appears to construct SQL statements "
                        "using dynamic string content. If user-controlled "
                        "input reaches this expression, an attacker may "
                        "modify the intended SQL query."
                    ),
                    recommendation=(
                        "Use parameterized queries or prepared statements. "
                        "Do not concatenate or interpolate untrusted input "
                        "into SQL statements."
                    )
                )
            )

    return findings


LINE_RULES = [
    {
        "title": "Unsafe HTML injection",
        "vulnerability_type": "Cross-Site Scripting",
        "severity": "High",
        "confidence": 0.84,
        "pattern": r"innerHTML\s*=|outerHTML\s*=|document\.write\s*\(|insertAdjacentHTML\s*\(|dangerouslySetInnerHTML|v-html\s*=|mark_safe\s*\(|\|\s*safe\b",
        "description": (
            "Untrusted content is written into HTML. If any part of "
            "this value comes from a request, an attacker can run script "
            "in the user's browser."
        ),
        "recommendation": (
            "Insert text instead of HTML, or sanitize with a dedicated "
            "HTML sanitizer before rendering."
        ),
    },
    {
        "title": "Command execution",
        "vulnerability_type": "Command Injection",
        "severity": "High",
        "confidence": 0.8,
        "pattern": r"os\.system\s*\(|shell\s*=\s*True|subprocess\.(run|call|Popen|check_output)\s*\(|child_process|Runtime\.getRuntime\(\)\.exec",
        "description": (
            "The program starts a shell or executes a command. If any "
            "argument includes request data, an attacker can run commands "
            "on the server."
        ),
        "recommendation": (
            "Call the program with a fixed argument list and never enable "
            "a shell. Reject unexpected characters in user input."
        ),
    },
    {
        "title": "Dynamic code execution",
        "vulnerability_type": "Code Injection",
        "severity": "High",
        "confidence": 0.86,
        "pattern": r"\beval\s*\(|\bexec\s*\(|new\s+Function\s*\(|pickle\.loads\s*\(|yaml\.load\s*\(",
        "description": (
            "This line executes or deserializes data as code. Untrusted "
            "input here can take over the process."
        ),
        "recommendation": (
            "Remove eval and exec. Use safe parsers such as json.loads "
            "or yaml.safe_load, and never unpickle data from users."
        ),
    },
    {
        "title": "Possible path traversal",
        "vulnerability_type": "Path Traversal",
        "severity": "Medium",
        "confidence": 0.74,
        "pattern": r"send_file\s*\(|send_from_directory\s*\(|open\s*\([^)]*request|path\.join\s*\([^)]*request|os\.path\.join\s*\([^)]*request",
        "description": (
            "A file path is built from request data. An attacker can use "
            "../ sequences to read or write files outside the intended folder."
        ),
        "recommendation": (
            "Resolve the path and confirm it stays inside a fixed directory "
            "before opening the file."
        ),
    },
    {
        "title": "Possible server-side request forgery",
        "vulnerability_type": "Server-Side Request Forgery",
        "severity": "Medium",
        "confidence": 0.72,
        "pattern": r"requests\.(get|post|put|delete|head)\s*\([^)]*request|urllib\.request\.urlopen\s*\(|http\.get\s*\([^)]*req\.",
        "description": (
            "The server fetches a URL that may come from the request. "
            "An attacker can make the server call internal services."
        ),
        "recommendation": (
            "Allow only known hosts and schemes, and block link-local "
            "and private addresses."
        ),
    },
    {
        "title": "Open redirect",
        "vulnerability_type": "Open Redirect",
        "severity": "Medium",
        "confidence": 0.76,
        "pattern": r"redirect\s*\(\s*request|res\.redirect\s*\(\s*req\.|location\s*=\s*request",
        "description": (
            "The redirect target comes from the request. An attacker can "
            "send users to a site they control."
        ),
        "recommendation": (
            "Redirect only to relative paths or a fixed list of hosts."
        ),
    },
    {
        "title": "Hardcoded credential",
        "vulnerability_type": "Hardcoded Secret",
        "severity": "High",
        "confidence": 0.9,
        "pattern": r"(?i)(password|passwd|secret|api[_-]?key|access[_-]?token|private[_-]?key|client[_-]?secret)\s*[:=]\s*['\"][^'\"]{6,}['\"]",
        "description": (
            "A credential is written directly in the file. Anyone with "
            "the source can reuse it."
        ),
        "recommendation": (
            "Load the value from the environment or a secret manager, "
            "and rotate the exposed credential."
        ),
    },
    {
        "title": "Embedded private key or cloud key",
        "vulnerability_type": "Hardcoded Secret",
        "severity": "Critical",
        "confidence": 0.95,
        "pattern": r"-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|sk_live_[0-9a-zA-Z]{10,}",
        "description": (
            "The file contains a private key or a live provider key."
        ),
        "recommendation": (
            "Remove the key from the repository, rotate it, and store "
            "the replacement outside source control."
        ),
    },
    {
        "title": "Weak hash or insecure randomness",
        "vulnerability_type": "Weak Cryptography",
        "severity": "Medium",
        "confidence": 0.7,
        "pattern": r"hashlib\.md5\s*\(|hashlib\.sha1\s*\(|MD5\s*\(|SHA1\s*\(|Math\.random\s*\(|random\.random\s*\(|MODE_ECB",
        "description": (
            "This uses a weak hash, ECB mode, or a non-cryptographic "
            "random generator. Those are not suitable for passwords, "
            "tokens, or session identifiers."
        ),
        "recommendation": (
            "Use a password hashing function such as bcrypt or argon2, "
            "and use a cryptographic random generator for secrets."
        ),
    },
    {
        "title": "TLS verification disabled",
        "vulnerability_type": "Insecure Transport",
        "severity": "Medium",
        "confidence": 0.88,
        "pattern": r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false|InsecureRequestWarning",
        "description": (
            "Certificate checks are turned off, so a network attacker "
            "can impersonate the remote server."
        ),
        "recommendation": (
            "Leave TLS verification enabled and trust a specific "
            "certificate instead of disabling checks."
        ),
    },
    {
        "title": "Debug mode enabled",
        "vulnerability_type": "Insecure Configuration",
        "severity": "Medium",
        "confidence": 0.8,
        "pattern": r"debug\s*=\s*True|DEBUG\s*=\s*True|app\.run\([^)]*debug\s*=\s*True",
        "description": (
            "Debug mode is on. It can expose stack traces, source, "
            "and an interactive console."
        ),
        "recommendation": (
            "Turn debug mode off outside local development."
        ),
    },
    {
        "title": "Permissive CORS policy",
        "vulnerability_type": "Insecure Configuration",
        "severity": "Low",
        "confidence": 0.75,
        "pattern": r"Access-Control-Allow-Origin['\"]?\s*[:=]\s*['\"]?\*|cors\(\s*\)|origin\s*:\s*['\"]\*['\"]",
        "description": (
            "Any website can call this API from a browser. Authenticated "
            "requests may be readable by other sites."
        ),
        "recommendation": (
            "Allow only the specific origins that should call this service."
        ),
    },
]


def line_is_placeholder(line):
    lowered = line.lower()
    placeholders = (
        "os.getenv",
        "os.environ",
        "process.env",
        "your_",
        "changeme",
        "placeholder",
        "${",
    )
    return any(marker in lowered for marker in placeholders)


def scan_line_rules(source_files):
    findings = []

    for source_file in source_files:
        file_path = source_file["file"]
        lines = source_file["content"].splitlines()

        for line_number, line in enumerate(lines, start=1):
            if line_is_placeholder(line):
                continue

            for rule in LINE_RULES:
                if not re.search(rule["pattern"], line, re.IGNORECASE):
                    continue

                findings.append(
                    create_rule_finding(
                        title=rule["title"],
                        vulnerability_type=rule["vulnerability_type"],
                        severity=rule["severity"],
                        confidence=rule["confidence"],
                        file_path=file_path,
                        line_number=line_number,
                        evidence=line.strip()[:500],
                        description=rule["description"],
                        recommendation=rule["recommendation"],
                    )
                )

    return findings


def run_rule_based_scans(source_files):
    findings = []

    findings.extend(
        scan_sql_injection_rules(source_files)
    )
    findings.extend(
        scan_line_rules(source_files)
    )

    return findings