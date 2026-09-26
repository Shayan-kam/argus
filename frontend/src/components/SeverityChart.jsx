import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts";


function SeverityChart({ summary }) {
  if (!summary) {
    return null;
  }

  const severityCounts = summary.severity_counts || {};

  const chartData = [
    {
      severity: "Critical",
      count: severityCounts.Critical || 0
    },
    {
      severity: "High",
      count: severityCounts.High || 0
    },
    {
      severity: "Medium",
      count: severityCounts.Medium || 0
    },
    {
      severity: "Low",
      count: severityCounts.Low || 0
    },
    {
      severity: "Info",
      count: severityCounts.Informational || 0
    }
  ];

  return (
    <section className="chart-panel">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">VULNERABILITY BREAKDOWN</p>

          <h2>Findings by Severity</h2>
        </div>
      </div>

      <div className="chart-container">
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={chartData}
            margin={{
              top: 10,
              right: 20,
              left: 0,
              bottom: 10
            }}
          >
            <CartesianGrid strokeDasharray="3 3"/>

            <XAxis dataKey="severity"/>

            <YAxis allowDecimals={false}/>

            <Tooltip />

            <Bar
              dataKey="count"
              name="Findings"
              radius={[6, 6, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}


export default SeverityChart;