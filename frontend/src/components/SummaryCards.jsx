function SummaryCards({ summary }) {
  if (!summary) {
    return null;
  }

  const severityCounts = summary.severity_counts || {};

  const cards = [
    {
      label: "Total Findings",
      value: summary.total_findings || 0,
      description: "Potential security issues"
    },
    {
      label: "Critical Findings",
      value: severityCounts.Critical || 0,
      description: "Require immediate attention"
    },
    {
      label: "High Findings",
      value: severityCounts.High || 0,
      description: "High-priority issues"
    },
    {
      label: "Scan Duration",
      value: `${summary.scan_duration_seconds || 0}s`,
      description: "Total analysis time"
    }
  ];

  return (
    <section className="summary-grid">
      {cards.map((card) => (
        <article
          className="summary-card"
          key={card.label}
          data-reveal
        >
          <p className="summary-label">{card.label}</p>

          <h2 className="summary-value">{card.value}</h2>

          <p className="summary-description">{card.description}</p>
        </article>
      ))}
    </section>
  );
}


export default SummaryCards;