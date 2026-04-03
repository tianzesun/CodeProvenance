import React, { useMemo } from "react";
import CodeHeatmapViewer from "./CodeHeatmapViewer";

/**
 * DualHeatmap - Side-by-side visual forensic code viewer.
 * Shows both submissions with heatmap overlays for matched regions.
 * 
 * Click any line to view evidence evidence in sidebar.
 * Red = high confidence, Orange = medium, Yellow = low.
 */
export default function DualHeatmap({ data, onSelectRegion }) {
  const { regions } = data || { regions: [] };
  
  // Build combined code with line numbers from both submissions
  const allSnippetsA = [...new Set((regions || []).map(r => r.a_snippet || "").filter(Boolean))];
  const allSnippetsB = [...new Set((regions || []).map(r => r.b_snippet || "").filter(Boolean))];
  
  // Build heat maps by line number for each side
  const heatMapA = useMemo(() => {
    const map = {};
    let lineNo = 1;
    allSnippetsA.forEach((snippet) => {
      const lines = snippet.split('\n');
      lines.forEach(() => {
        const matchingRegions = (regions || []).filter(r => r.a_snippet && r.a_snippet.includes(snippet));
        if (matchingRegions.length > 0) {
          map[lineNo] = Math.max(...matchingRegions.map(r => r.confidence));
        }
        lineNo++;
      });
    });
    return map;
  }, [regions]);
  
  const heatMapB = useMemo(() => {
    const map = {};
    let lineNo = 1;
    allSnippetsB.forEach((snippet) => {
      const lines = snippet.split('\n');
      lines.forEach(() => {
        const matchingRegions = (regions || []).filter(r => r.b_snippet && r.b_snippet.includes(snippet));
        if (matchingRegions.length > 0) {
          map[lineNo] = Math.max(...matchingRegions.map(r => r.confidence));
        }
        lineNo++;
      });
    });
    return map;
  }, [regions]);
  
  function getHeatColor(intensity) {
    if (intensity > 0.85) return "rgba(255, 0, 0, 0.25)";     // Red
    if (intensity > 0.70) return "rgba(255, 105, 0, 0.20)";  // Orange
    if (intensity > 0.50) return "rgba(255, 255, 0, 0.15)";  // Yellow
    return "transparent";
  }
  
  function renderCodePane(code, heatMap, side) {
    const lines = code.split('\n');
    return (
      <div className="font-mono text-sm border rounded p-2 bg-white overflow-auto max-h-[600px]">
        {lines.map((line, idx) => {
          const lineNo = idx + 1;
          const intensity = heatMap[lineNo] || 0;
          const matchingRegions = (regions || []).filter(r => {
            const snippet = side === "a" ? r.a_snippet : r.b_snippet;
            return snippet && snippet.split('\n').includes(line) && r.confidence > 0.5;
          });
          
          return (
            <div key={idx}
              className="flex hover:bg-gray-100 cursor-pointer"
              style={{ backgroundColor: getHeatColor(intensity) }}
              onClick={() => matchingRegions.length > 0 && onSelectRegion(matchingRegions[0])}
              title={matchingRegions.length > 0 ? `Confidence: ${matchingRegions[0].confidence} | Type: ${matchingRegions[0].type}` : `Line ${lineNo}`}
            >
              <div className="w-10 text-gray-400 select-none text-right pr-2 text-xs">
                {lineNo}
              </div>
              <pre className="flex-1 whitespace-pre-wrap">{line || " "}</pre>
            </div>
          );
        })}
      </div>
    );
  }
  
  return (
    <div className="grid grid-cols-2 gap-2">
      <div>
        <h3 className="font-bold mb-2 text-gray-700 px-2">Submission A</h3>
        {renderCodePane(allSnippetsA.join('\n'), heatMapA, "a")}
      </div>
      <div>
        <h3 className="font-bold mb-2 text-gray-700 px-2">Submission B</h3>
        {renderCodePane(allSnippetsB.join('\n'), heatMapB, "b")}
      </div>
    </div>
  );
}