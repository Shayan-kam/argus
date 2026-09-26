import { useState } from "react";
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts";


const SEVERITY_COLORS = {
  Critical: "#ffc1ce",
  High: "#ffd7b3",
  Medium: "#f7e6a7",
  Low: "#c0f4dd",
  Info: "#dfe7f4"
};

function severityClassName(severity) {
  if (severity === "Info") {
    return "informational";
  }

  return (severity || "informational").toLowerCase();
}

function SeverityTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) {
    return null;
  }

  const point = payload[0].payload;

  if (!point || point.severity == null) {
    return null;
  }

  const count = point.count || 0;

  return (
    <div className="severity-cursor-tooltip">
      <span className={`severity-badge severity-${severityClassName(point.severity)}`}>
        {point.severity}
      </span>
      <strong>{count}</strong>
      <span>{count === 1 ? "finding" : "findings"}</span>
    </div>
  );
}

const TOOLTIP_WIDTH = 176;
const TOOLTIP_HEIGHT = 44;
const TOOLTIP_OFFSET = 14;

function tooltipPositionFor(event) {
  const wrapper = event.currentTarget.querySelector(".recharts-wrapper");

  if (!wrapper) {
    return null;
  }

  const bounds = wrapper.getBoundingClientRect();
  const cursorX = event.clientX - bounds.left;
  const cursorY = event.clientY - bounds.top;
  let x = cursorX + TOOLTIP_OFFSET;
  let y = cursorY + TOOLTIP_OFFSET;

  if (x + TOOLTIP_WIDTH > bounds.width - 8) {
    x = cursorX - TOOLTIP_WIDTH - TOOLTIP_OFFSET;
  }

  if (y + TOOLTIP_HEIGHT > bounds.height - 8) {
    y = cursorY - TOOLTIP_HEIGHT - TOOLTIP_OFFSET;
  }

  return {
    x: Math.max(8, Math.min(x, bounds.width - TOOLTIP_WIDTH - 8)),
    y: Math.max(8, Math.min(y, bounds.height - TOOLTIP_HEIGHT - 8))
  };
}

function SeverityChart({ summary }) {
  const [tooltipPosition, setTooltipPosition] = useState(null);

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
    <section className="chart-panel" data-reveal>
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">VULNERABILITY BREAKDOWN</p>

          <h2>Findings by Severity</h2>
        </div>
      </div>

      <div
        className="chart-container"
        onMouseMove={(event) => {
          const nextPosition = tooltipPositionFor(event);

          if (nextPosition) {
            setTooltipPosition(nextPosition);
          }
        }}
        onMouseLeave={() => setTooltipPosition(null)}
      >
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

            <Tooltip
              content={SeverityTooltip}
              isAnimationActive={false}
              position={tooltipPosition || undefined}
              cursor={{ fill: "rgba(148, 163, 184, 0.12)" }}
              wrapperStyle={{ outline: "none" }}
            />

            <Bar
              dataKey="count"
              name="Findings"
              radius={[6, 6, 0, 0]}
            >
              {chartData.map((entry) => (
                <Cell
                  key={entry.severity}
                  fill={SEVERITY_COLORS[entry.severity]}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}


export default SeverityChart;
