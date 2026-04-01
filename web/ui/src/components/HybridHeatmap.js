import React, { useState, useMemo, useCallback } from "react";
import TokenHeatmapRenderer from "./TokenHeatmapRenderer";
import CodeHeatmapViewer from "./CodeHeatmapViewer";

/**
 * View mode types for the hybrid heatmap.
 */
const VIEW_MODES = {
  LINE: "line",
  TOKEN: "token",
  BOTH: "both",
};

/**
 * HybridHeatmap - Combines line-level and token-level heatmaps.
 * 
 * This component provides a comprehensive view of code similarity by combining:
 * 1. Line-level heatmap (coarse view) - Shows which lines have matches
 * 2. Token-level heatmap (fine view) - Shows exact tokens that matched
 * 
 * Users can toggle between three views:
 * - Line only: Traditional line-based highlighting
 * - Token only: Precise token-level highlighting
 * - Both: Side-by-side or tabbed view showing both perspectives
 * 
 * The token-level view eliminates false positives from:
 * - Boilerplate code being highlighted alongside actual matches
 * - Partial line matches showing as full line highlights
 * - Variable renaming obfuscation hiding structural similarity
 * 
 * Usage:
 * <HybridHeatmap
 *   codeA={sourceA}
 *   codeB={sourceB}
 *   lineHeatmap={lineData}           // Traditional line-based regions
 *   tokenSpansA={heatmapResult.spans_a}  // Token-level spans
 *   tokenSpansB={heatmapResult.spans_b}
 *   defaultView="both"
 * />
 * 
 * @param {Object} props
 * @param {string} props.codeA - Source code A
 * @param {string} props.codeB - Source code B
 * @param {Object} props.lineHeatmap - Line-based heatmap data {regions: [{a_range, b_range, confidence, type}]}
 * @param {Array} props.tokenSpansA - Token spans for code A
 * @param {Array} props.tokenSpansB - Token spans for code B
 * @param {string} props.defaultView - Initial view mode ('line' | 'token' | 'both')
 * @param {Function} props.onSelectRegion - Callback when region is selected
 * @param {Function} props.onHoverToken - Callback when token is hovered
 * @returns {JSX.Element}
 */
export default function HybridHeatmap({
  codeA,
  codeB,
  lineHeatmap,
  tokenSpansA = [],
  tokenSpansB = [],
  defaultView = VIEW_MODES.BOTH,
  onSelectRegion,
  onHoverToken,
}) {
  const [viewMode, setViewMode] = useState(defaultView);
  const [activePanel, setActivePanel] = useState("A"); // "A" or "B" for side-by-side
  const [selectedToken, setSelectedToken] = useState(null);

  // Handle token hover
  const handleTokenHover = useCallback(
    (token) => {
      setSelectedToken(token);
      if (onHoverToken) {
        onHoverToken(token);
      }
    },
    [onHoverToken]
  );

  // Determine if we should show both panels
  const showBothPanels = viewMode === VIEW_MODES.BOTH;

  // Compute stats for the info panel
  const stats = useMemo(() => {
    const aChars = codeA?.length || 0;
    const bChars = codeB?.length || 0;
    const aHighlighted = tokenSpansA.reduce((sum, s) => sum + (s.end - s.start), 0);
    const bHighlighted = tokenSpansB.reduce((sum, s) => sum + (s.end - s.start), 0);
    const lineRegions = lineHeatmap?.regions?.length || 0;

    return {
      A: {
        total: aChars,
        highlighted: aHighlighted,
        coverage: aChars > 0 ? ((aHighlighted / aChars) * 100).toFixed(1) : 0,
        spans: tokenSpansA.length,
      },
      B: {
        total: bChars,
        highlighted: bHighlighted,
        coverage: bChars > 0 ? ((bHighlighted / bChars) * 100).toFixed(1) : 0,
        spans: tokenSpansB.length,
      },
      lineRegions,
    };
  }, [codeA, codeB, tokenSpansA, tokenSpansB, lineHeatmap]);

  return (
    <div className="border rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <div className="border-b bg-gray-50 px-4 py-3">
        <div className="flex items-center justify-between">
          {/* Title */}
          <div className="flex items-center gap-3">
            <h3 className="font-semibold text-gray-800">Similarity Heatmap</h3>

            {/* View Mode Tabs */}
            <div className="flex rounded-md bg-gray-200 p-0.5 text-xs">
              <button
                className={`px-3 py-1 rounded ${
                  viewMode === VIEW_MODES.LINE
                    ? "bg-white shadow text-gray-900"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                onClick={() => setViewMode(VIEW_MODES.LINE)}
              >
                Line View
              </button>
              <button
                className={`px-3 py-1 rounded ${
                  viewMode === VIEW_MODES.TOKEN
                    ? "bg-white shadow text-gray-900"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                onClick={() => setViewMode(VIEW_MODES.TOKEN)}
              >
                Token View
              </button>
              <button
                className={`px-3 py-1 rounded ${
                  viewMode === VIEW_MODES.BOTH
                    ? "bg-white shadow text-gray-900"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                onClick={() => setViewMode(VIEW_MODES.BOTH)}
              >
                Hybrid
              </button>
            </div>
          </div>

          {/* Info badge */}
          <div className="text-xs text-gray-500">
            {viewMode === VIEW_MODES.LINE && `${stats.lineRegions} line regions detected`}
            {viewMode === VIEW_MODES.TOKEN && 
              `${stats.A.spans} token spans (A) · ${stats.B.spans} token spans (B)`}
            {viewMode === VIEW_MODES.BOTH && 
              `Line + Token: ${stats.lineRegions} regions, ${stats.A.spans + stats.B.spans} tokens`}
          </div>
        </div>
      </div>

      {/* Token info panel (shown when hovering) */}
      {selectedToken && (
        <div className="px-4 py-2 bg-blue-50 border-b text-xs text-blue-800 flex items-center justify-between">
          <div>
            <span className="font-medium">Token: {selectedToken.token_type || "unknown"}</span>
            <span className="mx-2">|</span>
            <span>Match Type: {selectedToken.match_type}</span>
            <span className="mx-2">|</span>
            <span>Confidence: {(selectedToken.confidence * 100).toFixed(1)}%</span>
            {selectedToken.explanation && (
              <>
                <span className="mx-2">|</span>
                <span>{selectedToken.explanation}</span>
              </>
            )}
          </div>
          <button
            className="text-gray-500 hover:text-gray-700"
            onClick={() => setSelectedToken(null)}
          >
            ✕
          </button>
        </div>
      )}

      {/* Content */}
      <div className="p-4">
        {/* Line View */}
        {viewMode === VIEW_MODES.LINE && (
          <div className="space-y-4">
            {codeA && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500" />
                  Source A
                  {codeA && (
                    <span className="text-xs text-gray-500">
                      ({stats.A.coverage}% highlighted)
                    </span>
                  )}
                </h4>
                <CodeHeatmapViewer
                  code={codeA}
                  heatmap={lineHeatmap}
                  onSelectRegion={onSelectRegion}
                />
              </div>
            )}
            {codeB && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  Source B
                  {codeB && (
                    <span className="text-xs text-gray-500">
                      ({stats.B.coverage}% highlighted)
                    </span>
                  )}
                </h4>
                <CodeHeatmapViewer
                  code={codeB}
                  heatmap={lineHeatmap}
                  onSelectRegion={onSelectRegion}
                />
              </div>
            )}
          </div>
        )}

        {/* Token View */}
        {viewMode === VIEW_MODES.TOKEN && (
          <div className="space-y-4">
            {/* Panel toggle for single view */}
            {!showBothPanels && (
              <div className="flex gap-2 mb-2">
                <button
                  className={`px-3 py-1 rounded text-xs font-medium ${
                    activePanel === "A"
                      ? "bg-blue-100 text-blue-800 border border-blue-300"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                  onClick={() => setActivePanel("A")}
                >
                  Source A ({stats.A.coverage}%)
                </button>
                <button
                  className={`px-3 py-1 rounded text-xs font-medium ${
                    activePanel === "B"
                      ? "bg-green-100 text-green-800 border border-green-300"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                  onClick={() => setActivePanel("B")}
                >
                  Source B ({stats.B.coverage}%)
                </button>
              </div>
            )}

            <div className={showBothPanels ? "grid grid-cols-2 gap-4" : ""}>
              {(showBothPanels || activePanel === "A") && codeA && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-500" />
                    Source A — Token Precision Mode
                  </h4>
                  <TokenHeatmapRenderer
                    code={codeA}
                    spans={tokenSpansA}
                    onHoverToken={handleTokenHover}
                    onClickToken={handleTokenHover}
                  />
                </div>
              )}
              {(showBothPanels || activePanel === "B") && codeB && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-500" />
                    Source B — Token Precision Mode
                  </h4>
                  <TokenHeatmapRenderer
                    code={codeB}
                    spans={tokenSpansB}
                    onHoverToken={handleTokenHover}
                    onClickToken={handleTokenHover}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Hybrid View - Both Side by Side */}
        {viewMode === VIEW_MODES.BOTH && (
          <div className="space-y-6">
            {/* Line Level (Coarse) */}
            <div className="border rounded p-3 bg-gray-50">
              <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                </svg>
                Line Heatmap (Coarse View)
              </h4>
              <div className="grid grid-cols-2 gap-4">
                {codeA && (
                  <div>
                    <span className="text-xs text-gray-500">Source A</span>
                    <CodeHeatmapViewer
                      code={codeA}
                      heatmap={lineHeatmap}
                      onSelectRegion={onSelectRegion}
                    />
                  </div>
                )}
                {codeB && (
                  <div>
                    <span className="text-xs text-gray-500">Source B</span>
                    <CodeHeatmapViewer
                      code={codeB}
                      heatmap={lineHeatmap}
                      onSelectRegion={onSelectRegion}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Token Level (Fine) */}
            <div className="border rounded p-3">
              <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Token-Level Precision Mode
              </h4>
              <div className="grid grid-cols-2 gap-4">
                {codeA && (
                  <div>
                    <span className="text-xs text-gray-500">Source A</span>
                    <TokenHeatmapRenderer
                      code={codeA}
                      spans={tokenSpansA}
                      onHoverToken={handleTokenHover}
                      onClickToken={handleTokenHover}
                    />
                  </div>
                )}
                {codeB && (
                  <div>
                    <span className="text-xs text-gray-500">Source B</span>
                    <TokenHeatmapRenderer
                      code={codeB}
                      spans={tokenSpansB}
                      onHoverToken={handleTokenHover}
                      onClickToken={handleTokenHover}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Export view modes for external use
export { VIEW_MODES };