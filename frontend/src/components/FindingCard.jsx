import { useState } from "react";


function FindingCard({ finding }) {
  const [expanded, setExpanded] = useState(false);

  const confidencePercentage = Math.round(
    (finding.confidence || 0) * 100
  );

  const severityClass = (
    finding.severity || "Informational"
  ).toLowerCase();

  return (
    <article className="finding-card" data-reveal>
      <div className="finding-header">
        <div className="finding-title-section">
          <h3>{finding.title}</h3>

          <p className="finding-location">
            File: {finding.file}; Line: {
              finding.line !== null && finding.line !== undefined
                ? finding.line
                : "Unknown"
            }
          </p>
        </div>

        <span className={`severity-badge severity-${severityClass}`}>
          {finding.severity}
        </span>
      </div>

      <p className="finding-description">
        {finding.description}
      </p>

      <div className="finding-meta">
        <span>
          <strong>Type:</strong>{" "}
          {finding.vulnerability_type}
        </span>

        <span>
          <strong>Confidence:</strong>{" "}
          {confidencePercentage}%
        </span>

        <span>
          <strong>Source:</strong>{" "}
          {finding.source || "ai"}
        </span>
      </div>

      <button className="secondary-button" onClick={() => setExpanded(!expanded)}>
        {expanded ? "Hide Details" : "View Evidence"}
      </button>

      {expanded && (
        <div className="finding-details">
          <div className="detail-section">
            <h4>Evidence</h4>
            <p>{finding.evidence}</p>
          </div>

          <div className="detail-section">
            <h4>Recommendation</h4>
            <p>{finding.recommendation}</p>
          </div>
        </div>
      )}
    </article>
  );
}


export default FindingCard;