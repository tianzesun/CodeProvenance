import React from "react";
export default function RiskSummaryCard({ summary }) {
  return (
    <div className="bg-white p-4 rounded-lg border shadow-sm">
      <div className="flex items-center justify-between">
        <div><h2 className="text-lg font-bold text-gray-800">Academic Integrity Risk Assessment</h2><p className="text-sm text-gray-500">Evidence-based similarity analysis</p></div>
        <div className="text-right">
          <span className={`text-2xl font-bold ${summary.risk_level === "HIGH" ? "text-red-600" : summary.risk_level === "MEDIUM" ? "text-orange-500" : "text-green-600"}`}>{summary.risk_level}</span>
          <p className="text-xs text-gray-500">{summary.total_blocks} matched blocks</p>
        </div>
      </div>
    </div>
  );
}
