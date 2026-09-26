"""
PDF report generation for Argus.
"""

import html
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak
)

from findings import SecurityFinding


def _safe(value) -> str:
    """
    Escapes HTML/XML entities (&, <, >) to avoid ReportLab Paragraph parser syntax errors.
    """
    if value is None:
        return ""
    return html.escape(str(value))


def generate_pdf_report(
    findings,
    output_path,
    repository_url
):
    """
    Generates a PDF report containing all security findings.

    Args:
        findings: List of SecurityFinding objects.
        output_path: Destination PDF path.
        repository_url: Repository analyzed.
    """

    document = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch
    )

    styles = getSampleStyleSheet()

    story = []

    # Report title.
    story.append(
        Paragraph(
            "Argus Security Analysis Report",
            styles["Title"]
        )
    )

    story.append(
        Spacer(1, 0.2 * inch)
    )

    story.append(
        Paragraph(
            f"<b>Repository:</b> {_safe(repository_url)}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Total Findings:</b> {len(findings)}",
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 0.3 * inch)
    )

    if not findings:

        story.append(
            Paragraph(
                "No security findings were identified.",
                styles["BodyText"]
            )
        )

    for index, finding in enumerate(findings, start=1):

        story.append(
            Paragraph(
                f"{index}. {_safe(finding.title)}",
                styles["Heading2"]
            )
        )

        story.append(
            Paragraph(
                f"<b>Vulnerability Type:</b> "
                f"{_safe(finding.vulnerability_type)}",
                styles["BodyText"]
            )
        )

        story.append(
            Paragraph(
                f"<b>Severity:</b> {_safe(finding.severity)}",
                styles["BodyText"]
            )
        )

        story.append(
            Paragraph(
                f"<b>Confidence:</b> "
                f"{round(finding.confidence * 100, 1)}%",
                styles["BodyText"]
            )
        )

        line_text = (
            str(finding.line)
            if finding.line is not None
            else "Unknown"
        )

        story.append(
            Paragraph(
                f"<b>Location:</b> "
                f"{_safe(finding.file)}, line {line_text}",
                styles["BodyText"]
            )
        )

        story.append(
            Spacer(1, 0.1 * inch)
        )

        story.append(
            Paragraph(
                f"<b>Evidence:</b> {_safe(finding.evidence)}",
                styles["BodyText"]
            )
        )

        story.append(
            Spacer(1, 0.1 * inch)
        )

        story.append(
            Paragraph(
                f"<b>Description:</b> {_safe(finding.description)}",
                styles["BodyText"]
            )
        )

        story.append(
            Spacer(1, 0.1 * inch)
        )

        story.append(
            Paragraph(
                f"<b>Recommendation:</b> "
                f"{_safe(finding.recommendation)}",
                styles["BodyText"]
            )
        )

        if index < len(findings):

            story.append(
                PageBreak()
            )

    document.build(story)