import React, { useMemo, useCallback } from "react";

/**
 * Token-level color palette for code highlighting.
 * 
 * Colors match the backend HeatIntensity enum:
 * - CRITICAL (>85%): Red - strong evidence of plagiarism
 * - HIGH (70-85%): Orange - significant similarity
 * - MEDIUM (50-70%): Yellow - moderate overlap
 * - LOW (30-50%): Light yellow - weak similarity
 * - NONE (<30%): Transparent - no match
 */
const INTENSITY_COLORS = {
  critical: "rgba(239, 68, 68, 0.35)",     // Red-500
  high: "rgba(249, 115, 22, 0.30)",        // Orange-500
  medium: "rgba(234, 179, 8, 0.25)",       // Yellow-500
  low: "rgba(250, 204, 21, 0.15)",         // Yellow-300
  none: "transparent",
};

/**
 * Convert confidence to color string.
 * 
 * @param {number} confidence - Similarity confidence [0, 1]
 * @returns {string} CSS color string
 */
function getConfidenceColor(confidence) {
  if (confidence > 0.85) return INTENSITY_COLORS.critical;
  if (confidence > 0.7) return INTENSITY_COLORS.high;
  if (confidence > 0.5) return INTENSITY_COLORS.medium;
  if (confidence > 0.3) return INTENSITY_COLORS.low;
  return INTENSITY_COLORS.none;
}

/**
 * Get intensity label for tooltip/legend.
 * 
 * @param {number} confidence - Similarity confidence [0, 1]
 * @returns {string} Human-readable intensity label
 */
function getIntensityLabel(confidence) {
  if (confidence > 0.85) return "Critical";
  if (confidence > 0.7) return "High";
  if (confidence > 0.5) return "Medium";
  if (confidence > 0.3) return "Low";
  return "None";
}

/**
 * TokenHeatmapRenderer - Character-level inline highlighting.
 * 
 * This component renders code with per-character highlighting based on
 * token spans from the backend. Unlike line-based heatmaps, this
 * highlights only the exact tokens that matched, eliminating false
 * positives from highlighting entire lines.
 * 
 * Key design decisions:
 * - Uses character-level spans (start, end offsets) for precise highlighting
 * - Handles overlapping spans with max-confidence resolution
 * - Memoized heatmap array generation for performance
 * - Only creates span elements for highlighted characters (optimization)
 * 
 * Usage:
 * <TokenHeatmapRenderer
 *   code={sourceCode}
 *   spans={heatmapResult.spans_a}
 *   onHoverToken={handleTokenHover}
 * />
 * 
 * @param {Object} props
 * @param {string} props.code - Source code to display
 * @param {Array} props.spans - Array of TokenSpan objects from backend
 * @param {Function} props.onHoverToken - Callback when hovering a highlighted token
 * @param {Function} props.onClickToken - Callback when clicking a highlighted token
 * @param {string} props.className - Additional CSS classes
 * @param {Object} props.style - Inline styles
 * @returns {JSX.Element} Rendered code with token-level highlighting
 */
export default function TokenHeatmapRenderer({
  code,
  spans = [],
  onHoverToken,
  onClickToken,
  className = "",
  style = {},
}) {
  // Build character-level heatmap array
  // Each index i contains max confidence of all spans covering character i
  const heatmapArray = useMemo(() => {
    if (!code || spans.length === 0) {
      return new Float32Array(code?.length || 0);
    }

    const map = new Float32Array(code.length);
    
    for (const span of spans) {
      const start = Math.max(0, span.start);
      const end = Math.min(code.length, span.end);
      const confidence = span.confidence || 0;
      
      for (let i = start; i < end; i++) {
        // Max-confidence resolution for overlapping spans
        map[i] = Math.max(map[i], confidence);
      }
    }
    
    return map;
  }, [code, spans]);

  // Build span metadata map for hover/click interactions
  const spanMetaMap = useMemo(() => {
    const metaMap = new Map();
    
    for (const span of spans) {
      const key = `${span.start}-${span.end}`;
      metaMap.set(key, {
        ...span,
        matchedValue: span.matched_value || code?.slice(span.start, span.end),
        intensityLabel: getIntensityLabel(span.confidence),
        color: getConfidenceColor(span.confidence),
      });
    }
    
    return metaMap;
  }, [spans, code]);

  // Find which span covers a character position
  const findSpanAtPosition = useCallback(
    (position) => {
      if (!position && position !== 0) return null;
      
      for (const span of spans) {
        if (position >= span.start && position < span.end) {
          const key = `${span.start}-${span.end}`;
          return spanMetaMap.get(key) || null;
        }
      }
      return null;
    },
    [spans, spanMetaMap]
  );

  // Handle character hover
  const handleCharacterEnter = useCallback(
    (charIndex) => {
      if (!onHoverToken) return;
      const span = findSpanAtPosition(charIndex);
      if (span) {
        onHoverToken(span);
      }
    },
    [findSpanAtPosition, onHoverToken]
  );

  // Handle character click
  const handleCharacterClick = useCallback(
    (charIndex) => {
      if (!onClickToken) return;
      const span = findSpanAtPosition(charIndex);
      if (span) {
        onClickToken(span);
      }
    },
    [findSpanAtPosition, onClickToken]
  );

  // Render code with token-level highlighting
  // Uses a single pre element with nested spans for each highlighted segment
  const renderedCode = useMemo(() => {
    if (!code) return null;

    const elements = [];
    let currentConfidence = -1;
    let currentSpan = null;
    let segmentBuffer = [];

    // Helper function to flush accumulated characters
    const flushSegment = () => {
      if (segmentBuffer.length === 0) return;

      const text = segmentBuffer.join("");
      const confidence = currentConfidence > 0 ? currentConfidence : 0;
      const bgColor = getConfidenceColor(confidence);
      const spanKey = `seg-${elements.length}`;

      if (confidence > 0 && currentSpan) {
        // Highlighted segment - make interactive
        elements.push(
          <span
            key={spanKey}
            style={{
              backgroundColor: bgColor,
              borderBottom: "2px solid rgba(0,0,0,0.1)",
              cursor: onClickToken ? "pointer" : "default",
            }}
            onClick={() => handleCharacterClick(currentSpan.start)}
            onMouseEnter={() => handleCharacterEnter(currentSpan.start)}
            className="rounded-sm"
          >
            {text}
          </span>
        );
      } else {
        // Non-highlighted segment
        elements.push(<span key={spanKey}>{text}</span>);
      }

      segmentBuffer = [];
    };

    for (let i = 0; i < code.length; i++) {
      const confidence = heatmapArray[i] || 0;
      
      // Check if we need to start a new segment
      const confChanged = Math.round(confidence * 10) !== Math.round(currentConfidence * 10);
      
      if (confChanged && currentConfidence !== -1) {
        flushSegment();
      }

      currentConfidence = confidence;
      currentSpan = findSpanAtPosition(i);
      segmentBuffer.push(code[i]);
    }

    // Flush remaining characters
    flushSegment();

    return elements;
  }, [
    code,
    heatmapArray,
    findSpanAtPosition,
    handleCharacterEnter,
    handleCharacterClick,
    onClickToken,
  ]);

  // Calculate coverage stats for display
  const stats = useMemo(() => {
    if (!code) return null;
    
    const totalChars = code.length;
    const highlightedChars = Array.from(heatmapArray).filter((v) => v > 0).length;
    const coveragePercent = totalChars > 0 ? ((highlightedChars / totalChars) * 100).toFixed(1) : 0;
    
    return {
      totalChars,
      highlightedChars,
      coveragePercent,
      spanCount: spans.length,
    };
  }, [code, heatmapArray, spans]);

  if (!code) {
    return (
      <div className="text-gray-500 italic p-4 border rounded">
        No source code available
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      {/* Coverage banner (optional, shown when stats available) */}
      {stats && stats.spanCount > 0 && (
        <div className="mb-2 px-2 py-1 bg-gray-50 border-b text-xs text-gray-600 flex items-center justify-between">
          <span>
            🔥 {stats.spanCount} highlighted regions ({stats.coveragePercent}% coverage)
          </span>
          <Legend />
        </div>
      )}

      {/* Code display */}
      <pre
        className="font-mono text-sm leading-6 whitespace-pre-wrap bg-gray-50 border rounded p-3 overflow-auto max-h-[600px]"
        style={style}
      >
        {renderedCode}
      </pre>
    </div>
  );
}

/**
 * Color legend component for the heatmap.
 */
function Legend() {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="font-medium">Heat:</span>
      <span className="flex items-center gap-1">
        <span
          className="inline-block w-3 h-3 rounded"
          style={{ backgroundColor: INTENSITY_COLORS.critical }}
        />
        Critical
      </span>
      <span className="flex items-center gap-1">
        <span
          className="inline-block w-3 h-3 rounded"
          style={{ backgroundColor: INTENSITY_COLORS.high }}
        />
        High
      </span>
      <span className="flex items-center gap-1">
        <span
          className="inline-block w-3 h-3 rounded"
          style={{ backgroundColor: INTENSITY_COLORS.medium }}
        />
        Medium
      </span>
      <span className="flex items-center gap-1">
        <span
          className="inline-block w-3 h-3 rounded"
          style={{ backgroundColor: INTENSITY_COLORS.low }}
        />
        Low
      </span>
    </div>
  );
}