import FindingCard from "./FindingCard";

const SEVERITY_ORDER = {
    Critical: 0,
    High: 1,
    Medium: 2,
    Low: 3,
    Informational: 4
};

function FindingsSection({ findings }) {
    const orderedFindings = [...findings].sort((left, right) => {
        const leftRank = SEVERITY_ORDER[left.severity] ?? SEVERITY_ORDER.Informational;
        const rightRank = SEVERITY_ORDER[right.severity] ?? SEVERITY_ORDER.Informational;

        if (leftRank !== rightRank) {
            return leftRank - rightRank;
        }

        return (right.confidence || 0) - (left.confidence || 0);
    });

    return (
        <section className="findings-section">
            <div className="section-heading-inline" data-reveal>
                <h2>Potential Vulnerabilities</h2>
                <span className="count-pill">{findings.length}</span>
            </div>

            {orderedFindings.length === 0 ? (
                <div className="empty-state">
                    No potential vulnerabilities were identified.
                </div>
            ) : (
                <div className="findings-list">
                    {orderedFindings.map((finding) => (
                        <FindingCard key={finding.id} finding={finding} />
                    ))}
                </div>
            )}
        </section>
    );
}

export default FindingsSection;
