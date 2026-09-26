import { useState } from "react";
import "./App.css";
import SummaryCards from "./components/SummaryCards";
import SeverityChart from "./components/SeverityChart";
import FindingCard from "./components/FindingCard";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
    const [repositoryUrl, setRepositoryUrl] = useState("");
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

        if (!repositoryUrl.trim()) {
            setError("Please enter a GitHub repository URL.");
            return;
        }

        setProgress(INITIAL_PROGRESS);
        setLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/api/analyze`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    repository_url: repositoryUrl,
                    scan_profile: "standard"
                })
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

    const selectedAgents = Array.isArray(scanData?.routing?.selected_agents)
        ? scanData.routing.selected_agents.map((item) => {
            if (typeof item === "string") {
                return item;
            }

            return item?.agent?.name || item?.agent_name || "Agent";
        }).filter(Boolean)
        : [];

    const skippedAgents = Array.isArray(scanData?.routing?.skipped_agents)
        ? scanData.routing.skipped_agents.map((item) => item?.agent_name || item?.agent || "Skipped agent")
        : [];

    const preprocessingSignals = Array.isArray(scanData?.preprocessing?.signals)
        ? scanData.preprocessing.signals
        : [];

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
            <div className="container">
                <header className="hero-panel">
                    <div className="brand-row">
                        <div className="brand-mark">A</div>
                        <div>
                            <p className="eyebrow">AI SECURITY ANALYSIS</p>
                            <h1>Argus</h1>
                        </div>
                    </div>

                    <p className="subtitle">
                        AI-powered source code security analysis for public repositories
                    </p>
                </header>

                <div className="input-section">
                    <input
                        type="text"
                        value={repositoryUrl}
                        onChange={(event) => setRepositoryUrl(event.target.value)}
                        placeholder="https://github.com/user/repository"
                        disabled={loading}
                    />

                    <button onClick={analyzeRepository} disabled={loading}>
                        {loading ? "Analyzing..." : "Analyze Repository"}
                    </button>
                </div>

                {loading && (
                    <div className="loading-panel progress-panel" aria-live="polite">
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

                {error && <div className="error">{error}</div>}

                {!loading && !error && scanId && (
                    <section className="results-section">
                        <div className="results-header">
                            <div>
                                <p className="section-eyebrow">SCAN COMPLETE</p>
                                <h2>Security Overview</h2>
                                <p className="results-subtitle">
                                    {findings.length} potential security finding{findings.length === 1 ? "" : "s"} across the analyzed repository.
                                </p>
                            </div>

                            <button className="primary-button" onClick={downloadReport}>
                                Download PDF Report
                            </button>
                        </div>

                        <div className="meta-grid">
                            <div className="meta-card">
                                <span className="meta-label">Repository</span>
                                <strong>{scanData?.repository_url || repositoryUrl}</strong>
                            </div>
                            <div className="meta-card">
                                <span className="meta-label">Files analyzed</span>
                                <strong>{scanData?.files_analyzed ?? findings.length}</strong>
                            </div>
                            <div className="meta-card">
                                <span className="meta-label">Scan profile</span>
                                <strong>{scanData?.scan_profile || "standard"}</strong>
                            </div>
                            <div className="meta-card">
                                <span className="meta-label">Runtime</span>
                                <strong>{scanData?.timing?.total_seconds ?? 0}s</strong>
                            </div>
                        </div>

                        <div className="insight-grid">
                            <div className="insight-panel">
                                <p className="section-eyebrow">ROUTING</p>
                                <h3>Triggered agents</h3>
                                {selectedAgents.length > 0 ? (
                                    <div className="chip-list">
                                        {selectedAgents.map((agentName) => (
                                            <span key={agentName} className="chip chip-success">{agentName}</span>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="muted">No specialized agents were triggered.</p>
                                )}

                                {skippedAgents.length > 0 && (
                                    <div className="skip-panel">
                                        <h4>Skipped</h4>
                                        <div className="chip-list">
                                            {skippedAgents.slice(0, 4).map((agentName) => (
                                                <span key={agentName} className="chip chip-muted">{agentName}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div className="insight-panel">
                                <p className="section-eyebrow">PREPROCESSING</p>
                                <h3>Detected signals</h3>
                                {preprocessingSignals.length > 0 ? (
                                    <div className="chip-list">
                                        {preprocessingSignals.map((signal) => (
                                            <span key={signal} className="chip chip-info">{signal}</span>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="muted">No strong security signals were detected.</p>
                                )}
                            </div>
                        </div>

                        <SummaryCards summary={displaySummary} />
                        <SeverityChart summary={{ severity_counts: severitySummary }} />

                        <section className="findings-section">
                            <div className="section-heading-inline">
                                <h2>Potential Vulnerabilities</h2>
                                <span className="count-pill">{findings.length}</span>
                            </div>

                            {findings.length === 0 ? (
                                <div className="empty-state">
                                    No potential vulnerabilities were identified.
                                </div>
                            ) : (
                                <div className="findings-list">
                                    {findings.map((finding) => (
                                        <FindingCard key={finding.id} finding={finding} />
                                    ))}
                                </div>
                            )}
                        </section>
                    </section>
                )}
            </div>
        </div>
    );
}

export default App;