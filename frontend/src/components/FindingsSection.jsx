import FindingCard from "./FindingCard";

function FindingsSection({ findings }) {
    return (
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
    );
}

export default FindingsSection;
