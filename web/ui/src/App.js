import React, { useState } from "react";
import DualHeatmap from "./components/DualHeatmap";
import EvidenceSidebar from "./components/EvidenceSidebar";
import RiskSummaryCard from "./components/RiskSummaryCard";

// Demo data with full code and regions
const DEMO_DATA = {
  a_code: `def calculate_average(data):
    total = sum(data)
    count = len(data)
    return total / count

def calculate_sum(data):
    total = 0
    for item in data:
        total += item
    return total
`,
  b_code: `def compute_mean(values):
    total = sum(values)
    count = len(values)
    return total / count

def compute_total(values):
    total = 0
    for v in values:
        total += v
    return total
`,
  summary: { total_blocks: 2, risk_level: "HIGH" },
  diff: {
    total_matches: 2,
    regions: [
      {
        a_range: [1, 4], b_range: [1, 4], confidence: 0.95, type: "ast",
        a_snippet: "def calculate_average(data):\n    total = sum(data)\n    count = len(data)\n    return total / count",
        b_snippet: "def compute_mean(values):\n    total = sum(values)\n    count = len(values)\n    return total / count",
        explanation: "Structural similarity detected (AST node alignment). Control flow and logic structure are similar, which is strong evidence of copying."
      },
      {
        a_range: [5, 9], b_range: [5, 9], confidence: 0.88, type: "fused",
        a_snippet: "def calculate_sum(data):\n    total = 0\n    for item in data:\n        total += item\n    return total",
        b_snippet: "def compute_total(values):\n    total = 0\n    for v in values:\n        total += v\n    return total",
        explanation: "Combined structural + lexical similarity detected. Multiple independent engines confirm match — strong evidence."
      }
    ]
  }
};

export default function App() {
  const [selected, setSelected] = useState(null);
  const [data] = useState(DEMO_DATA);

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-slate-800 text-white p-4 shadow">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold">IntegrityDesk</h1>
          <p className="text-sm text-gray-300">Visual Forensic Code Analysis System</p>
        </div>
      </header>

      <div className="max-w-7xl mx-auto p-4">
        <RiskSummaryCard summary={data.summary} />

        <div className="mt-4 mb-4">
          <DualHeatmap
            data={data.diff}
            codeA={data.a_code}
            codeB={data.b_code}
            onSelectRegion={setSelected}
          />
        </div>

        <div className="mt-4">
          <EvidenceSidebar selected={selected} regions={data.diff.regions} />
        </div>
      </div>
    </div>
  );
}