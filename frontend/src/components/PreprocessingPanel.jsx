function PreprocessingPanel({ preprocessing }) {
    const signals = Array.isArray(preprocessing?.signals)
        ? preprocessing.signals
        : [];

    const languages = Array.isArray(preprocessing?.languages)
        ? preprocessing.languages
        : [];

    return (
        <div className="insight-panel">
            <p className="section-eyebrow">PREPROCESSING</p>
            <h3>Detected signals</h3>

            {languages.length > 0 && (
                <div className="language-row">
                    <span className="option-label">Languages</span>
                    <div className="chip-list">
                        {languages.map((language) => (
                            <span key={language} className="chip chip-info">
                                {language}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {signals.length > 0 ? (
                <div className="chip-list">
                    {signals.map((signal) => (
                        <span key={signal} className="chip chip-info">
                            {signal}
                        </span>
                    ))}
                </div>
            ) : (
                <p className="muted">No strong security signals were detected.</p>
            )}

            {preprocessing?.total_signal_count > 0 && (
                <p className="signal-count muted">
                    {preprocessing.total_signal_count} total signal match
                    {preprocessing.total_signal_count === 1 ? "" : "es"}
                </p>
            )}
        </div>
    );
}

export default PreprocessingPanel;
