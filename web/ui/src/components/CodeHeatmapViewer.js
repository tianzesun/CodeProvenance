import React, { useMemo } from "react";

/**
 * CodeHeatmapViewer - Visual forensic overlay on source code.
 * 
 * Unlike MOSS/Turnitin which show reports, this shows:
 * - Red (>85% confidence): Suspicious logic duplication
 * - Orange (70-85%): Partial similarity  
 * - Yellow (50-70%): Weak overlap
 * - Transparent: No match detected
 * 
 * Click any line to view evidence details in sidebar.
 */
export default function CodeHeatmapViewer({ code, heatmap, onSelectRegion }) {
  const lines = useMemo(() => code.split('\n'), [code]);
  
  // Build heat map by line number
  const heatMapByLine = useMemo(() => {
    const map = {};
    if (!heatmap || !heatmap.regions) return map;
    
    heatmap.regions.forEach((r) => {
      const intensity = r.confidence;
      const range = r.a_range;
      for (let i = range[0]; i <= range[1]; i++) {
        map[i] = Math.max(map[i] || 0, intensity);
        // Store region metadata for click-to-evidence
        if (!map[`${i}_meta`]) {
          map[`${i}_meta`] = r;
        }
      }
    });
    return map;
  }, [heatmap]);
  
  function getHeatColor(intensity) {
    if (intensity > 0.85) return "rgba(255, 0, 0, 0.25)";     // Red
    if (intensity > 0.70) return "rgba(255, 105, 0, 0.20)";  // Orange
    if (intensity > 0.50) return "rgba(255, 255, 0, 0.15)";  // Yellow
    return "transparent";
  }
  
  return (
    <div className="font-mono text-sm border rounded p-2 bg-white overflow-auto max-h-[600px]">
      {lines.map((line, idx) => {
        const lineNo = idx + 1;
        const intensity = heatMapByLine[lineNo] || 0;
        const meta = heatMapByLine[`${lineNo}_meta`];
        
        return (
          <div key={idx}
            className="flex hover:bg-gray-100 cursor-pointer"
            style={{ backgroundColor: getHeatColor(intensity) }}
            onClick={() => meta && onSelectRegion(meta)}
            title={meta ? `Confidence: ${meta.confidence} | Type: ${meta.type}` : `Line ${lineNo}`}
          >
            <div className="w-12 text-gray-400 select-none text-right pr-2 text-xs">
              {lineNo}
            </div>
            <pre className="flex-1 whitespace-pre-wrap">{line || " "}</pre>
          </div>
        );
      })}
    </div>
  );
}