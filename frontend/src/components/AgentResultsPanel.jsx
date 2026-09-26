const STATUS_STYLES = {
    completed: "chip-success",
    skipped: "chip-muted",
    failed: "chip-danger"
};

function AgentResultsPanel({ agentResults }) {
    if (!Array.isArray(agentResults) || agentResults.length === 0) {
        return null;
    }

    return (
        <section className="agent-results-panel">
            <div className="section-heading-inline">
                <div>
                    <p className="section-eyebrow">AGENT OUTPUT</p>
                    <h2>Agent Results</h2>
                </div>
                <span className="count-pill">{agentResults.length}</span>
            </div>

            <div className="agent-results-grid">
                {agentResults.map((result) => {
                    const statusClass = STATUS_STYLES[result.status] || "chip-info";

                    return (
                        <article key={result.agent_name} className="agent-result-card">
                            <div className="agent-result-header">
                                <h3>{result.agent_name}</h3>
                                <span className={`chip ${statusClass}`}>
                                    {result.status}
                                </span>
                            </div>

                            <div className="agent-result-stats">
                                <div className="stat">
                                    <span className="stat-label">Findings</span>
                                    <strong>{result.findings_count ?? 0}</strong>
                                </div>
                                <div className="stat">
                                    <span className="stat-label">Runtime</span>
                                    <strong>{result.elapsed_seconds ?? 0}s</strong>
                                </div>
                                <div className="stat">
                                    <span className="stat-label">Files</span>
                                    <strong>
                                        {Array.isArray(result.files_analyzed)
                                            ? result.files_analyzed.length
                                            : 0}
                                    </strong>
                                </div>
                            </div>

                            {result.reason && result.status !== "completed" && (
                                <p className="agent-result-reason">{result.reason}</p>
                            )}

                            {Array.isArray(result.files_analyzed)
                                && result.files_analyzed.length > 0 && (
                                <details className="agent-files-details">
                                    <summary>Files analyzed</summary>
                                    <ul>
                                        {result.files_analyzed.map((filePath) => (
                                            <li key={filePath}>{filePath}</li>
                                        ))}
                                    </ul>
                                </details>
                            )}
                        </article>
                    );
                })}
            </div>
        </section>
    );
}

export default AgentResultsPanel;
