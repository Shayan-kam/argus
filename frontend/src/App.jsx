import { useState } from "react";
import "./App.css";
import argusLogo from "./assets/argus-eye.jpg";
import SummaryCards from "./components/SummaryCards";
import SeverityChart from "./components/SeverityChart";
import ScanForm from "./components/ScanForm";
import MetaGrid from "./components/MetaGrid";
import AgentRoutingPanel from "./components/AgentRoutingPanel";
import AgentResultsPanel from "./components/AgentResultsPanel";
import PreprocessingPanel from "./components/PreprocessingPanel";
import FindingsSection from "./components/FindingsSection";
import ScrollReveal from "./components/ScrollReveal";
import AudioForensics from "./components/AudioForensics";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function normalizeRepositoryUrl(repositoryUrl) {
    const trimmed = repositoryUrl.trim();

    try {
        const parsed = new URL(trimmed);
        const host = parsed.hostname.replace(/^www\./, "");

        if (host !== "github.com") {
            return trimmed;
        }

        const parts = parsed.pathname.split("/").filter(Boolean);

        if (parts.length < 2) {
            return trimmed;
        }

        const repository = parts[1].replace(/\.git$/, "");

        return `https://github.com/${parts[0]}/${repository}`;
    } catch {
        return trimmed;
    }
}

const INITIAL_PROGRESS = {
    percent: 1,
    message: "Starting the scan",
    updates: [
        {
            id: 1,
            message: "Starting the scan",
            current: true
        }
    ]
};

function App() {
    const [workspace, setWorkspace] = useState("repository");
    const [repositoryUrl, setRepositoryUrl] = useState("");
    const [scanProfile, setScanProfile] = useState("standard");
    const [githubToken, setGithubToken] = useState("");
    const [showTokenField, setShowTokenField] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [findings, setFindings] = useState([]);
    const [scanId, setScanId] = useState(null);
    const [scanData, setScanData] = useState(null);
    const [progress, setProgress] = useState(INITIAL_PROGRESS);

    async function analyzeRepository() {
        setError("");
        setFindings([]);
        setScanId(null);
        setScanData(null);

        const cleanedRepositoryUrl = normalizeRepositoryUrl(repositoryUrl);

        if (!cleanedRepositoryUrl) {
            const message = "Please enter a GitHub repository URL.";
            setError(message);
            throw new Error(message);
        }

        setRepositoryUrl(cleanedRepositoryUrl);
        setProgress(INITIAL_PROGRESS);
        setLoading(true);

        try {
            const body = {
                repository_url: cleanedRepositoryUrl,
                scan_profile: scanProfile
            };

            if (githubToken.trim()) {
                body.github_token = githubToken.trim();
            }

            const response = await fetch(`${API_BASE_URL}/api/analyze`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                const data = await response.json();
                const detail = data.detail;
                const message = typeof detail === "string"
                    ? detail
                    : "Analysis failed.";
                throw new Error(message);
            }

            if (!response.body) {
                throw new Error("The scan did not return progress updates.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let completed = false;

            while (!completed) {
                const { value, done } = await reader.read();

                if (done) {
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                const chunks = buffer.split("\n\n");
                buffer = chunks.pop() || "";

                for (const chunk of chunks) {
                    const line = chunk
                        .split("\n")
                        .find((entry) => entry.startsWith("data: "));

                    if (!line) {
                        continue;
                    }

                    const event = JSON.parse(line.slice(6));

                    if (event.type === "progress") {
                        setProgress((current) => {
                            const nextMessage = event.message || current.message;
                            const messageChanged = nextMessage !== current.message;
                            const updates = messageChanged
                                ? [
                                    ...current.updates.map((item) => ({
                                        ...item,
                                        current: false
                                    })),
                                    {
                                        id: current.updates.length + 1,
                                        message: nextMessage,
                                        current: true
                                    }
                                ]
                                : current.updates;

                            return {
                                percent: Math.max(current.percent, event.percent || 0),
                                message: nextMessage,
                                updates
                            };
                        });
                        continue;
                    }

                    if (event.type === "error") {
                        throw new Error(event.detail || "Analysis failed.");
                    }

                    if (event.type === "complete") {
                        const data = event.result || {};
                        setScanData(data);
                        setFindings(data.findings || []);
                        setScanId(data.scan_id);
                        completed = true;
                    }
                }
            }

            if (!completed) {
                throw new Error("The scan ended before it finished.");
            }
        } catch (err) {
            setError(err.message || "Something went wrong.");
            throw err;
        } finally {
            setLoading(false);
        }
    }

    function downloadReport() {
        if (!scanId) {
            return;
        }

        const reportUrl = scanData?.report_url
            ? `${API_BASE_URL}${scanData.report_url}`
            : `${API_BASE_URL}/api/report/${scanId}`;

        window.open(reportUrl, "_blank");
    }

    const severitySummary = scanData?.summary?.severity || {
        Critical: 0,
        High: 0,
        Medium: 0,
        Low: 0,
        Informational: 0
    };

    const displaySummary = {
        total_findings: scanData?.summary?.total_findings ?? findings.length,
        severity_counts: severitySummary,
        scan_duration_seconds: scanData?.timing?.total_seconds ?? 0
    };

    return (
        <div className="app-shell">
            <div className="visual-backdrop" aria-hidden="true">
                <MoltenMetal
                    color1="#0c2650"
                    color2="#103571"
                    color3="#739fe9"
                    speed={0.35}
                    scale={4}
                    detail={3}
                    glow={1.6}
                    coreSize={0.1}
                    swirl={1}
                    fold={-0.2}
                    blackPoint={0.05}
                    brightness={1.3}
                    colorMode="molten"
                    grain={true}
                    grainIntensity={0.05}
                    mouseInteraction={true}
                    mouseStrength={0.2}
                    opacity={1.0}
                />
            </div>
            <ScrollReveal />
            <div className="container">
                <header className="hero-panel" data-reveal>
                    <div className="brand-row">
                        <img className="brand-mark" src={argusLogo} alt="Argus" />
                        <div>
                            <p className="eyebrow">AI SECURITY ANALYSIS</p>
                            <h1>Argus</h1>
                        </div>
                    </div>

                    <p className="subtitle">
                        Gemini-powered source code security analysis for public
                        and private GitHub repositories.
                        <br />
                        Audio forensics reviews recordings for possible edits, generated speech, and other changes.
                    </p>
                </header>

                <nav className="workspace-nav" data-reveal aria-label="Analysis workspace">
                    <button
                        type="button"
                        className={workspace === "repository" ? "is-active" : ""}
                        aria-pressed={workspace === "repository"}
                        onClick={() => setWorkspace("repository")}
                    >
                        GitHub Security Analysis
                    </button>
                    <button
                        type="button"
                        className={workspace === "audio" ? "is-active" : ""}
                        aria-pressed={workspace === "audio"}
                        onClick={() => setWorkspace("audio")}
                    >
                        Audio Forensics
                    </button>
                </nav>

                <div hidden={workspace !== "audio"}>
                    <AudioForensics apiBaseUrl={API_BASE_URL} />
                </div>

                <div hidden={workspace !== "repository"}>
                <ScanForm
                    repositoryUrl={repositoryUrl}
                    onRepositoryUrlChange={setRepositoryUrl}
                    scanProfile={scanProfile}
                    onScanProfileChange={setScanProfile}
                    githubToken={githubToken}
                    onGithubTokenChange={setGithubToken}
                    showTokenField={showTokenField}
                    onToggleTokenField={() => setShowTokenField((value) => !value)}
                    loading={loading}
                    onSubmit={analyzeRepository}
                />

                {loading && (
                    <div className="loading-panel progress-panel" data-reveal aria-live="polite">
                        <div className="progress-copy">
                            <p className="section-eyebrow">ANALYSIS IN PROGRESS</p>
                            <h3>{progress.message}</h3>
                        </div>

                        <div
                            className="progress-track"
                            role="progressbar"
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-valuenow={Math.round(progress.percent)}
                            aria-label={progress.message}
                        >
                            <div
                                className="progress-fill"
                                style={{ width: `${Math.min(progress.percent, 100)}%` }}
                            />
                        </div>

                        <ul className="progress-log">
                            {progress.updates.map((update) => (
                                <li
                                    key={update.id}
                                    className={update.current ? "current" : "done"}
                                >
                                    {update.message}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {error && <div className="error" data-reveal>{error}</div>}

                {!loading && !error && scanId && (
                    <section className="results-section">
                        <div className="results-header" data-reveal>
                            <div>
                                <p className="section-eyebrow">SCAN COMPLETE</p>
                                <h2>Security Overview</h2>
                                <p className="results-subtitle">
                                    {findings.length} potential security finding
                                    {findings.length === 1 ? "" : "s"} across the
                                    analyzed repository.
                                </p>
                            </div>

                            <button className="primary-button" onClick={downloadReport}>
                                Download PDF Report
                            </button>
                        </div>

                        <MetaGrid
                            scanData={scanData}
                            repositoryUrl={repositoryUrl}
                        />

                        <div className="insight-grid">
                            <AgentRoutingPanel routing={scanData?.routing} />
                            <PreprocessingPanel preprocessing={scanData?.preprocessing} />
                        </div>

                        <AgentResultsPanel agentResults={scanData?.agent_results} />

                        <SummaryCards summary={displaySummary} />
                        <SeverityChart summary={{ severity_counts: severitySummary }} />

                        <FindingsSection findings={findings} />
                    </section>
                )}
                </div>
            </div>
        </div>
    );
}

export default App;
