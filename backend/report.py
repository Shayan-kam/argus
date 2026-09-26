"""
PDF report generation for Argus.
"""

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
            f"<b>Repository:</b> {repository_url}",
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
                f"{index}. {finding.title}",
                styles["Heading2"]
            )
        )

        story.append(
            Paragraph(
                f"<b>Vulnerability Type:</b> "
                f"{finding.vulnerability_type}",
                styles["BodyText"]
            )
        )

        story.append(
            Paragraph(
                f"<b>Severity:</b> {finding.severity}",
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
                f"{finding.file}, line {line_text}",
                styles["BodyText"]
            )
        )

        story.append(
            Spacer(1, 0.1 * inch)
        )

        story.append(
            Paragraph(
                f"<b>Evidence:</b> {finding.evidence}",
                styles["BodyText"]
            )
        )

        story.append(
            Spacer(1, 0.1 * inch)
        )

        story.append(
            Paragraph(
                f"<b>Description:</b> {finding.description}",
                styles["BodyText"]
            )
        )

        story.append(
            Spacer(1, 0.1 * inch)
        )

        story.append(
            Paragraph(
                f"<b>Recommendation:</b> "
                f"{finding.recommendation}",
                styles["BodyText"]
            )
        )

        if index < len(findings):

            story.append(
                PageBreak()
            )

    document.build(story)