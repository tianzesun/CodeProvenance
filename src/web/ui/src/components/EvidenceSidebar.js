import React from "react";

export default function EvidenceSidebar({ selected, regions }) {
  if (!selected) return (
    <div className="bg-white p-4 rounded-lg border shadow-sm flex items-center justify-center text-gray-400">
      Click a region to view evidence
    </div>
  );

  return (
    <div className="bg-white p-4 rounded-lg border shadow-sm space-y-4">
      <h3 className="font-bold text-gray-800 border-b pb-2">Evidence Block</h3>
      
      {/* Confidence */}
      <div>
        <span className="text-sm font-semibold text-gray-600">Confidence:</span>
        <span className={`ml-2 px-2 py-1 rounded text-sm font-bold ${
          selected.confidence > 0.85 ? "bg-red-100 text-red-800" :
          selected.confidence > 0.70 ? "bg-orange-100 text-orange-800" :
          "bg-yellow-100 text-yellow-800"
        }`}>
          {selected.confidence.toFixed(2)}
        </span>
      </div>

      {/* Match Type */}
      <div>
        <span className="text-sm font-semibold text-gray-600">Type:</span>
        <span className="ml-2 text-sm capitalize">{selected.type}</span>
      </div>

      {/* Engine Arbitration */}
      <div className="pt-2 border-t">
        <span className="text-sm font-semibold text-gray-600">Statistical Arbitration:</span>
        <div className="space-y-1 mt-1">
          {selected.evidence && selected.evidence.map((ev, idx) => (
            <div key={idx} className="flex justify-between text-xs">
              <span className="text-gray-500">{ev.name}:</span>
              <span className="font-mono">{ev.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Engine Diagnosis */}
      <div>
        <span className="text-sm font-semibold text-gray-600">Engine Diagnosis:</span>
        <div className="space-y-1 mt-1">
          {selected.explanation && Array.isArray(selected.explanation) ? (
            selected.explanation.map((exp, idx) => (
              <div key={idx} className="text-xs bg-gray-50 p-1 rounded border">
                <span className="font-semibold uppercase">{exp.engine}:</span> {exp.score} 
                <span className="text-gray-400 ml-2">(contrib: {exp.contribution})</span>
              </div>
            ))
          ) : (
            <p className="text-sm text-gray-700 leading-relaxed">{selected.explanation}</p>
          )}
        </div>
      </div>

      {/* Line Ranges */}
      <div className="pt-2 border-t">
        <span className="text-sm font-semibold text-gray-600">Matched Ranges:</span>
        <pre className="text-xs text-gray-700 mt-1 bg-gray-50 p-2 rounded">
{`A: lines ${selected.a_range[0]} - ${selected.a_range[1]}
B: lines ${selected.b_range[0]} - ${selected.b_range[1]}`}
        </pre>
      </div>

      {/* Snippets */}
      <div>
        <span className="text-sm font-semibold text-gray-600">Submission A Code:</span>
        <pre className="text-xs text-gray-700 mt-1 bg-gray-50 p-2 rounded max-h-40 overflow-auto whitespace-pre-wrap">
          {selected.a_snippet}
        </pre>
        <span className="text-sm font-semibold text-gray-600 mt-2 block">Submission B Code:</span>
        <pre className="text-xs text-gray-700 mt-1 bg-gray-50 p-2 rounded max-h-40 overflow-auto whitespace-pre-wrap">
          {selected.b_snippet}
        </pre>
      </div>

      <div className="text-xs text-gray-400 pt-2 border-t">
        This system produces forensic evidence, not verdicts. All findings require human review.
      </div>
    </div>
  );
}