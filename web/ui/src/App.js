import React, { useState } from "react";
import SideBySideDiff from "./components/SideBySideDiff";
import EvidenceSidebar from "./components/EvidenceSidebar";
import RiskSummaryCard from "./components/RiskSummaryCard";

const DEFAULT_DATA = {
  summary: { total_blocks: 3, risk_level: "HIGH", confidence: 0.91 },
  diff: {
    total_matches: 3,
    regions: [
      { a_range: [1, 5], b_range: [1, 5], confidence: 0.95, type: "ast",
        a_snippet: "def calculate_average(data):\n    total = sum(data)\n    count = len(data)\n    return total / count",
        b_snippet: "def compute_mean(values):\n    total = sum(values)\n    count = len(values)\n    return total / count",
        explanation: "Structural similarity detected (AST node alignment). Control flow and logic structure are similar, which is strong evidence of copying." },
      { a_range: [7, 12], b_range: [7, 12], confidence: 0.88, type: "token",
        a_snippet: "def calculate_sum(data):\n    total = 0\n    for item in data:\n        total += item\n    return total",
        b_snippet: "def compute_total(values):\n    total = 0\n    for v in values:\n        total += v\n    return total",
        explanation: "High token sequence overlap detected. This may indicate shared boilerplate or copied code." },
      { a_range: [7, 12], b_range: [13, 18], confidence: 0.72, type: "fused",
        a_snippet: "def calculate_sum(data):\n    total = 0\n    for item in data:\n        total += item\n    return total",
        b_snippet: "...additional code region...",
        explanation: "Combined structural + lexical similarity detected. Multiple independent engines confirm match." }
    ]
  }
};

export default function App() {
  const [selected, setSelected] = useState(null);
  const [data] = useState(DEFAULT_DATA);
  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-slate-800 text-white p-4 shadow">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold">IntegrityDesk</h1>
          <p className="text-sm text-gray-300">Academic Integrity Evidence Review System</p>
        </div>
      </header>
      <div className="max-w-7xl mx-auto p-4">
        <RiskSummaryCard summary={data.summary} />
        <div className="grid grid-cols-12 gap-4 mt-4">
          <div className="col-span-12 lg:col-span-9">
            <SideBySideDiff data={data.diff} onSelectRegion={setSelected} />
          </div>
          <div className="col-span-12 lg:col-span-3">
            <EvidenceSidebar selected={selected} />
          </div>
        </div>
      </div>
    </div>
  );
}
