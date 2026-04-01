import React from "react";
export default function EvidenceSidebar({ selected }) {
  if (!selected) return <div className="bg-white p-4 rounded-lg border shadow-sm h-full flex items-center justify-center text-gray-400">Click a region to view evidence</div>;
  return (
    <div className="bg-white p-4 rounded-lg border shadow-sm space-y-4">
      <h3 className="font-bold text-gray-800 border-b pb-2">Evidence Block</h3>
      <div><span className="text-sm font-semibold text-gray-600">Confidence:</span><span className={`ml-2 px-2 py-1 rounded text-sm font-bold ${selected.confidence > 0.85 ? "bg-red-100 text-red-800" : selected.confidence > 0.70 ? "bg-orange-100 text-orange-800" : "bg-yellow-100 text-yellow-800"}`}>{selected.confidence}</span></div>
      <div><span className="text-sm font-semibold text-gray-600">Type:</span><span className="ml-2 text-sm capitalize">{selected.type}</span></div>
      <div><span className="text-sm font-semibold text-gray-600">Explanation:</span><p className="text-sm text-gray-700 mt-1">{selected.explanation}</p></div>
      <div className="pt-2 border-t"><span className="text-sm font-semibold text-gray-600">Ranges:</span><pre className="text-xs text-gray-700 mt-1 bg-gray-50 p-2 rounded">{`A: ${selected.a_range[0]}-${selected.a_range[1]}\nB: ${selected.b_range[0]}-${selected.b_range[1]}`}</pre></div>
      <div className="text-xs text-gray-400 pt-2 border-t">This system produces evidence, not verdicts. All findings require human review.</div>
    </div>
  );
}
