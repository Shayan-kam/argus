"""
Argus FastAPI backend.

Responsibilities:
- Accept a public GitHub repository URL.
- Clone the repository.
- Run the optimized security-analysis orchestrator.
- Generate a PDF report.
- Return findings, routing information, and performance metrics.
"""

import json
import queue
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from github import clone_repository
from orchestrator import SecurityOrchestrator
from report import generate_pdf_report


app = FastAPI(
    title="Argus Security Scanner",
    version="1.0.0"
)


# Allow the React frontend to communicate with FastAPI.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


security_orchestrator = SecurityOrchestrator()


# Store generated reports during the current server session.
REPORT_DIRECTORY = Path("reports")
REPORT_DIRECTORY.mkdir(exist_ok=True)


class AnalyzeRequest(BaseModel):
    repository_url: str = Field(
        ...,
        min_length=1,
        description="Public GitHub repository URL"
    )

    scan_profile: str = Field(
        default="standard",
        description="quick, standard, or deep"
    )


def serialize_findings(findings):
    """
    Convert Pydantic SecurityFinding objects into JSON-compatible data.
    """

    serialized_findings = []

    for finding in findings:
        if hasattr(finding, "model_dump"):
            serialized_findings.append(
                finding.model_dump()
            )
        else:
            serialized_findings.append(finding)

    return serialized_findings


def calculate_severity_summary(findings):
    """
    Count findings by severity.
    """

    summary = {
        "Critical": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0,
        "Informational": 0
    }

    for finding in findings:
        severity = finding.get("severity")

        if severity in summary:
            summary[severity] += 1

    return summary


BASELINE_SECONDS = {
    "quick": 20,
    "standard": 75,
    "deep": 90,
}


def estimate_remaining_seconds(elapsed, percent, scan_profile):
    """
    Blend a profile baseline with the time already spent.

    Early stages stay close to the baseline. Later stages trust
    the observed pace, so the estimate tightens as the scan moves.
    """

    baseline = BASELINE_SECONDS.get(scan_profile, 75)

    if percent >= 99:
        return 0

    if percent <= 3:
        return max(1, round(baseline - elapsed))

    observed_total = elapsed / (percent / 100.0)
    trust = min(1.0, max(0.0, (percent - 8) / 40.0))
    estimated_total = (
        baseline * (1 - trust)
        + observed_total * trust
    )

    return max(1, round(estimated_total - elapsed))


def progress_event(percent, message, elapsed, scan_profile):
    return {
        "type": "progress",
        "percent": round(percent, 1),
        "message": message,
        "elapsed_seconds": round(elapsed, 1),
        "estimated_remaining_seconds": estimate_remaining_seconds(
            elapsed,
            percent,
            scan_profile
        ),
    }


def execute_scan(request, scan_id, temporary_directory, on_progress):
    """
    Clone a repository, analyze it, and write the PDF report.
    """

    print(
        f"\nStarting scan for: "
        f"{request.repository_url}"
    )

    print(
        f"Scan profile: {request.scan_profile}"
    )

    if request.scan_profile == "quick":
        on_progress(2, 16, "Cloning the repository")
    else:
        on_progress(2, 12, "Cloning the repository")

    repository_path = clone_repository(
        repository_url=request.repository_url,
        destination_directory=temporary_directory
    )

    analysis_result = (
        security_orchestrator.analyze_repository(
            repository_path=repository_path,
            scan_profile=request.scan_profile,
            on_progress=on_progress
        )
    )

    findings = analysis_result.get(
        "findings",
        []
    )

    serialized_findings = serialize_findings(
        findings
    )

    severity_summary = calculate_severity_summary(
        serialized_findings
    )

    if request.scan_profile == "quick":
        on_progress(90, 99, "Writing the PDF report")
    else:
        on_progress(94, 99, "Writing the PDF report")

    report_path = REPORT_DIRECTORY / (
        f"{scan_id}.pdf"
    )

    generate_pdf_report(
        findings=findings,
        output_path=str(report_path),
        repository_url=request.repository_url
    )

    routing = analysis_result.get(
        "routing",
        {}
    )

    agent_results = analysis_result.get(
        "agent_results",
        []
    )

    repository_analysis = analysis_result.get(
        "repository_analysis",
        {}
    )

    return {
        "scan_id": scan_id,
        "repository_url": request.repository_url,
        "scan_profile": request.scan_profile,

        "files_analyzed": analysis_result.get(
            "files_collected",
            0
        ),

        "findings": serialized_findings,

        "summary": {
            "total_findings": len(serialized_findings),
            "severity": severity_summary,
            "rule_findings": analysis_result.get(
                "rule_findings",
                0
            ),
            "llm_findings": analysis_result.get(
                "llm_findings",
                0
            )
        },

        "routing": routing,

        "preprocessing": {
            "languages": repository_analysis.get(
                "languages",
                []
            ),
            "signals": list(
                repository_analysis.get(
                    "signals",
                    {}
                ).keys()
            ),
            "total_signal_count": repository_analysis.get(
                "total_signal_count",
                0
            )
        },

        "agent_results": agent_results,

        "timing": analysis_result.get(
            "timing",
            {}
        ),

        "report_url": (
            f"/api/report/{scan_id}"
        )
    }


def stream_scan(request, scan_id, temporary_directory):
    """
    Run a scan on a background thread and yield live progress events.
    """

    events = queue.Queue()
    started_at = time.perf_counter()

    def on_progress(percent, ceiling, message):
        events.put({
            "type": "progress",
            "percent": percent,
            "ceiling": ceiling,
            "message": message,
        })

    def worker():
        try:
            result = execute_scan(
                request,
                scan_id,
                temporary_directory,
                on_progress
            )
            events.put({
                "type": "complete",
                "result": jsonable_encoder(result),
            })
        except Exception as error:
            print(
                f"Scan failed: {error}"
            )
            events.put({
                "type": "error",
                "detail": str(error),
            })
        finally:
            shutil.rmtree(
                temporary_directory,
                ignore_errors=True
            )

    threading.Thread(
        target=worker,
        daemon=True
    ).start()

    displayed_percent = 1.0
    ceiling = 4.0
    message = "Starting the scan"

    yield encode_event(
        progress_event(
            displayed_percent,
            message,
            0,
            request.scan_profile
        )
    )

    while True:
        try:
            item = events.get(timeout=0.4)
        except queue.Empty:
            gap = ceiling - displayed_percent

            if gap > 0.3:
                displayed_percent = min(
                    ceiling,
                    displayed_percent + max(0.3, gap * 0.07)
                )

            elapsed = time.perf_counter() - started_at
            yield encode_event(
                progress_event(
                    displayed_percent,
                    message,
                    elapsed,
                    request.scan_profile
                )
            )
            continue

        elapsed = time.perf_counter() - started_at

        if item["type"] == "progress":
            displayed_percent = max(
                displayed_percent,
                float(item["percent"])
            )
            ceiling = max(
                displayed_percent,
                float(item["ceiling"])
            )
            message = item["message"]
            yield encode_event(
                progress_event(
                    displayed_percent,
                    message,
                    elapsed,
                    request.scan_profile
                )
            )
            continue

        if item["type"] == "error":
            yield encode_event({
                "type": "error",
                "detail": item["detail"],
            })
            return

        yield encode_event(
            progress_event(
                100,
                "Scan complete",
                elapsed,
                request.scan_profile
            )
        )
        yield encode_event({
            "type": "complete",
            "result": item["result"],
        })
        return


def encode_event(payload):
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/")
def root():
    return {
        "name": "Argus Security Scanner",
        "status": "running"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.post("/api/analyze")
def analyze_repository(request: AnalyzeRequest):
    """
    Clone and analyze a GitHub repository.

    The response is a stream of progress events, followed by the
    finished scan or an error event.
    """

    allowed_profiles = {
        "quick",
        "standard",
        "deep"
    }

    if request.scan_profile not in allowed_profiles:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid scan profile. "
                "Choose quick, standard, or deep."
            )
        )

    temporary_directory = tempfile.mkdtemp(
        prefix="argus_scan_"
    )

    scan_id = str(uuid.uuid4())

    return StreamingResponse(
        stream_scan(
            request,
            scan_id,
            temporary_directory
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/report/{scan_id}")
def download_report(scan_id: str):
    """
    Return a generated PDF report.
    """

    report_path = REPORT_DIRECTORY / (
        f"{scan_id}.pdf"
    )

    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    return FileResponse(
        path=str(report_path),
        media_type="application/pdf",
        filename=f"argus-report-{scan_id}.pdf"
    )