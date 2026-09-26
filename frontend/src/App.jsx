import { useState } from "react";
import "./App.css";
import SummaryCards from "./components/SummaryCards";
import SeverityChart from "./components/SeverityChart";
import ScanForm from "./components/ScanForm";
import LoadingPanel from "./components/LoadingPanel";
import MetaGrid from "./components/MetaGrid";
import AgentRoutingPanel from "./components/AgentRoutingPanel";
import AgentResultsPanel from "./components/AgentResultsPanel";
import PreprocessingPanel from "./components/PreprocessingPanel";
import FindingsSection from "./components/FindingsSection";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
    const [repositoryUrl, setRepositoryUrl] = useState("");
    const [scanProfile, setScanProfile] = useState("standard");
    const [githubToken, setGithubToken] = useState("");
    const [showTokenField, setShowTokenField] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [findings, setFindings] = useState([]);
    const [scanId, setScanId] = useState(null);
    const [scanData, setScanData] = useState(null);

    async function analyzeRepository() {
        setError("");
        setFindings([]);
        setScanId(null);
        setScanData(null);

        if (!repositoryUrl.trim()) {
            setError("Please enter a GitHub repository URL.");
            return;
        }

        setLoading(true);

        try {
            const body = {
                repository_url: repositoryUrl,
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

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Analysis failed.");
            }

            setScanData(data);
            setFindings(data.findings || []);
            setScanId(data.scan_id);
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
                        Gemini-powered source code security analysis for public
                        and private GitHub repositories
                    </p>
                </header>

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

                {loading && <LoadingPanel />}

                {error && <div className="error">{error}</div>}

                {!loading && !error && scanId && (
                    <section className="results-section">
                        <div className="results-header">
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
    );
}

export default App;
