import React from "react";
export default function SideBySideDiff({ data, onSelectRegion }) {
  const { regions } = data;
  return (
    <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
      <div className="grid grid-cols-2 border-b bg-gray-50">
        <div className="p-3 font-bold text-gray-700">Submission A</div>
        <div className="p-3 font-bold text-gray-700">Submission B</div>
      </div>
      <div className="grid grid-cols-2">
        <CodePane regions={regions} side="a" onSelectRegion={onSelectRegion} />
        <CodePane regions={regions} side="b" onSelectRegion={onSelectRegion} />
      </div>
    </div>
  );
}
function CodePane({ regions, side, onSelectRegion }) {
  function confColor(c) {
    if (c > 0.85) return "rgba(220,53,69,0.12)";
    if (c > 0.70) return "rgba(255,165,0,0.12)";
    return "rgba(255,230,0,0.10)";
  }
  const lines = regions.map((r, idx) => ({
    ...r, idx, range: side === "a" ? r.a_range : r.b_range,
    snippet: side === "a" ? r.a_snippet : r.b_snippet
  })).sort((a, b) => a.range[0] - b.range[0]);
  return (
    <div className="font-mono text-xs border-r last:border-r-0 overflow-auto max-h-[600px]">
      {lines.map((line) => (
        <div key={line.idx} onClick={() => onSelectRegion(line)}
          className="cursor-pointer p-1 border-b hover:brightness-95"
          style={{ backgroundColor: confColor(line.confidence) }}
          title={`Confidence: ${line.confidence} | Type: ${line.type}`}>
          <div className="flex">
            <span className="w-12 text-gray-400 select-none text-right pr-2">{line.range[0]}-{line.range[1]}</span>
            <pre className="whitespace-pre-wrap flex-1">{line.snippet}</pre>
          </div>
        </div>
      ))}
    </div>
  );
}
