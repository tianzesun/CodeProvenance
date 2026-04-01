import React from "react";

/**
 * EvidenceSidebar - Shows detailed evidence for a selected match region.
 */
export default function EvidenceSidebar({ selected, regions }) {
  if (!selected) return (
    <div className="bg-white p-4 rounded-lg border shadow-sm h-full flex items-center justify-center text-gray-400">
      Click a matched line to view evidence
    </div>
  );

  return (
    <div className="bg-white p-4 rounded-lg border shadow-sm space-y-4">
      <h3 className="font-bold text-gray-800 border-b pb-2">Evidence Evidence</h3>
      
      {/* Matched Region Info */}
      <div>
        <span className="text-sm font-semibold text-gray-600">Matched Region:</span>
        <div className="text-sm text-gray-700 mt-1">
          <div><b>Submission A:</b> Lines {selected.a_range?.[0]}-{selected.a_range?.[1]}</div>
          <div><b>Submission B:</b> Lines {selected.b_range?.[0]}-{selected.b_range?.[1]}</div>
        </div>
      </div>
      
      {/* Confidence */}
      <div>
        <span className="text-sm font-semibold text-gray-600">Confidence:</span>
        <span className={`ml-2 px-2 py-1 rounded text-sm font-bold ${
          selected.confidence > 0.85 ? "bg-red-100 text-red-800" :
          selected.confidence > 0.70 ? "bg-orange-100 text-orange-800" :
          "bg-yellow-100 text-yellow-800"
        }`}>
          {selected.confidence}
        </span>
      </div>

      {/* Match Type */}
      <div>
        <span className="text-sm font-semibold text-gray-600">Match Type:</span>
        <span className="ml-2 text-sm capitalize">{selected.type}</span>
      </div>

      {/* Explanation */}
      <div>
        <span className="text-sm font-semibold text-gray-600">Explanation:</span>
        <p className="text-sm text-gray-700 mt-1 leading-relaxed">
          {selected.explanation}
        </p>
      </div>

      {/* Code Snippets */}
      <div className="pt-2 border-t">
        <span className="text-sm font-semibold text-gray-600">Matched Code:</span>
        <div className="mt-1">
          <div className="text-xs font-semibold text-gray-600 mb-1">
            <pre className="text-xs text-gray-700 bg-gray-50 p-2 rounded whitespace-pre-wrap">
              {selected.a_snippet}
            </pre>
          </div>
          <div className="text-xs text-gray-400 mt-1 border-t pt-1">
            <span className="text-sm font-semibold text-gray-600">Submission B:</span>
            <pre className="text-xs text-gray-700 bg-gray-50 p-2 rounded whitespace-pre-wrap">
              {selected.b_snippet}
            </pre>
          </div>
        </div>
      </div>

      <div className="text-xs text-gray-400 pt-2 border-t">
        This system produces forensic evidence, not verdicts. All findings require human review.
      </div>
    </div>
  );
}
</write_to_file>
<write_to_file>
<path>web/ui/src/components/RiskSummaryCard.js</path>
<content>import React from "react";

/**
 * RiskSummaryCard - Overall risk assessment for the submission pair.
 */
export default function RiskSummaryCard({ summary }) {
  return (
    <div className="bg-white p-4 rounded-lg border shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-gray-800">IntegrityDesk Risk Assessment</h2>
          <p className="text-sm text-gray-500">Visual forensic code analysis</p>
        </div>
        <div className="text-right">
          <span className={`text-2xl font-bold ${
            summary.risk_level === "HIGH" ? "text-red-600" :
            summary.risk_level === "MEDIUM" ? "text-orange-500" :
            "text-green-600"
          }`}>
            {summary.risk_level}
          </span>
          <p className="text-xs text-gray-500">{summary.total_blocks} matched regions</p>
        </div>
      </div>
    </div>
  );
}