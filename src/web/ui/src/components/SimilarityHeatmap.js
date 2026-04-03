import React, { useMemo } from 'react';
import Plot from 'react-plotly.js';

/**
 * SimilarityHeatmap - Visualize large-scale similarity across submission pairs.
 * Provides intuitive evidence for professors to spot clusters of copying.
 */
const SimilarityHeatmap = ({ submissions, similarityMatrix }) => {
    const data = useMemo(() => {
        const labels = submissions.map(s => s.name);
        
        return [{
            z: similarityMatrix,
            x: labels,
            y: labels,
            type: 'heatmap',
            colorscale: 'YlOrRd',
            showscale: true,
            hoverongaps: false,
            hoverlabel: { bgcolor: "#fff", font: { color: "#333" } },
            hovertemplate: 'Source A: %{y}<br>Source B: %{x}<br>Similarity: %{z:.2f}<extra></extra>'
        }];
    }, [submissions, similarityMatrix]);

    const layout = {
        title: {
            text: 'Forensic Similarity Matrix',
            font: { family: 'Inter, sans-serif', size: 18, color: '#1e293b' }
        },
        autosize: true,
        margin: { l: 100, r: 50, b: 100, t: 50, pad: 4 },
        xaxis: { 
            title: 'Submissions',
            tickangle: -45,
            gridcolor: '#e2e8f0'
        },
        yaxis: { 
            title: 'Submissions',
            gridcolor: '#e2e8f0'
        },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
    };

    return (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <Plot
                data={data}
                layout={layout}
                useResizeHandler={true}
                style={{ width: "100%", height: "600px" }}
                config={{ displayModeBar: false, responsive: true }}
            />
            <div className="mt-4 flex items-center gap-4 text-xs text-slate-500">
                <div className="flex items-center gap-1">
                    <span className="w-3 h-3 bg-red-600 rounded-sm"></span>
                    <span>High Risk (>0.85)</span>
                </div>
                <div className="flex items-center gap-1">
                    <span className="w-3 h-3 bg-orange-400 rounded-sm"></span>
                    <span>Moderate Risk (0.5-0.85)</span>
                </div>
                <div className="flex items-center gap-1">
                    <span className="w-3 h-3 bg-yellow-100 border border-slate-200 rounded-sm"></span>
                    <span>Baseline (Coincidence)</span>
                </div>
            </div>
        </div>
    );
};

export default SimilarityHeatmap;
