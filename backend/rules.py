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


def run_rule_based_scans(source_files):
    findings = []

    findings.extend(
        scan_sql_injection_rules(source_files)
    )

    return findings