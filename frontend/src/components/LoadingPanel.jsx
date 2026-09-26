function LoadingPanel() {
    return (
        <div className="loading-panel" aria-live="polite">
            <div className="loading-visual">
                <div className="orbit orbit-one" />
                <div className="orbit orbit-two" />
                <div className="core" />
            </div>

            <div className="loading-copy">
                <h3>Running repo analysis</h3>
                <p>
                    Cloning the repository, detecting signals, routing Gemini agents,
                    and evaluating the highest-risk code paths.
                </p>
            </div>

            <div className="loading-steps">
                <span className="step active">Fetch</span>
                <span className="step active">Signal scan</span>
                <span className="step active">Agent review</span>
                <span className="step">Report</span>
            </div>
        </div>
    );
}

export default LoadingPanel;
