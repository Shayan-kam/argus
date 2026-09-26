from pydantic import BaseModel, Field
from typing import Literal, Optional
from uuid import uuid4


class SecurityFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))

    title: str
    vulnerability_type: str

    severity: Literal[
        "Critical",
        "High",
        "Medium",
        "Low",
        "Informational"
    ]

    confidence: float = Field(ge=0.0, le=1.0)

    file: str
    line: Optional[int] = None

    evidence: str
    description: str
    recommendation: str

    source: Literal[
        "ai",
        "rule-based",
        "hybrid"
    ] = "ai"


def normalize_severity(severity):
    """
    Converts inconsistent model output into accepted severity values.
    """

    if not severity:
        return "Informational"

    normalized = severity.strip().lower()

    severity_map = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "moderate": "Medium",
        "low": "Low",
        "info": "Informational",
        "informational": "Informational"
    }

    return severity_map.get(normalized, "Informational")


def normalize_confidence(confidence):
    """
    Converts confidence into a number between 0 and 1.
    """

    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        return 0.5

    # Some models may return 94 instead of 0.94.
    if confidence > 1:
        confidence = confidence / 100

    return max(0.0, min(1.0, confidence))


def normalize_finding(raw_finding):

    if isinstance(raw_finding, SecurityFinding):
        return raw_finding

    return SecurityFinding(
        title=raw_finding.get(
            "title",
            "Potential Security Issue"
        ),

        vulnerability_type=raw_finding.get(
            "vulnerability_type",
            raw_finding.get("type", "Unknown")
        ),

        severity=normalize_severity(
            raw_finding.get("severity")
        ),

        confidence=normalize_confidence(
            raw_finding.get("confidence")
        ),

        file=raw_finding.get(
            "file",
            "Unknown file"
        ),

        line=raw_finding.get("line"),

        evidence=raw_finding.get(
            "evidence",
            "No evidence provided."
        ),

        description=raw_finding.get(
            "description",
            "No description provided."
        ),

        recommendation=raw_finding.get(
            "recommendation",
            "Review this code manually."
        ),

        source="ai"
    )


def deduplicate_findings(findings):
    """
    Removes duplicate findings based on:
    vulnerability type + file + line.
    """

    unique_findings = []
    seen = set()

    for finding in findings:
        key = (
            finding.vulnerability_type.lower(),
            finding.file,
            finding.line
        )

        if key not in seen:
            seen.add(key)
            unique_findings.append(finding)

    return unique_findings