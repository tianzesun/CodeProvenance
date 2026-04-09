// @ts-nocheck
'use client';

import { Brain, AlertTriangle, CheckCircle2, TrendingUp, FileCode, Sparkles } from 'lucide-react';

/**
 * AI Detection Panel Component
 * Displays AI-generated code detection results with visual indicators
 */

export function AIDetectionScore({ probability, confidence, indicators = [] }) {
  const getRiskLevel = (prob) => {
    if (prob >= 0.8) return { level: 'Very High', color: 'red', tone: 'critical' };
    if (prob >= 0.6) return { level: 'High', color: 'orange', tone: 'warning' };
    if (prob >= 0.4) return { level: 'Medium', color: 'yellow', tone: 'caution' };
    if (prob >= 0.2) return { level: 'Low', color: 'blue', tone: 'low' };
    return { level: 'Very Low', color: 'green', tone: 'safe' };
  };

  const risk = getRiskLevel(probability);
  const confidencePercent = Math.round(confidence * 100);

  const toneMap = {
    critical: 'border-red-500/20 bg-red-500/[0.08] text-red-600',
    warning: 'border-orange-500/20 bg-orange-500/[0.08] text-orange-600',
    caution: 'border-yellow-500/20 bg-yellow-500/[0.08] text-yellow-600',
    low: 'border-blue-600/20 bg-blue-600/[0.08] text-blue-600',
    safe: 'border-emerald-500/20 bg-emerald-500/[0.08] text-emerald-600',
  };

  const dotMap = {
    critical: 'bg-red-500',
    warning: 'bg-orange-500',
    caution: 'bg-yellow-500',
    low: 'bg-blue-600',
    safe: 'bg-emerald-500',
  };

  return (
    <div className={`rounded-[24px] border px-5 py-5 ${toneMap[risk.tone]}`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Brain size={18} />
            <span className="text-sm font-semibold">AI Detection Analysis</span>
          </div>
          
          <div className="flex items-center gap-3">
            <div className={`h-4 w-4 rounded-full ${dotMap[risk.tone]}`} />
            <span className="text-3xl font-bold">{Math.round(probability * 100)}%</span>
            <span className="text-sm font-medium">AI Probability</span>
          </div>

          <div className="text-sm">
            Risk Level: <span className="font-semibold">{risk.level}</span>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <TrendingUp size={14} />
            <span>Confidence: {confidencePercent}%</span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {indicators.slice(0, 3).map((indicator, idx) => (
            <span
              key={idx}
              className="inline-flex items-center gap-1 rounded-full border border-current px-2 py-1 text-xs font-medium opacity-80"
            >
              <AlertTriangle size={10} />
              {indicator.length > 40 ? `${indicator.slice(0, 40)}...` : indicator}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export function AIDetectionSummary({ results }) {
  if (!results || results.length === 0) {
    return (
      <div className="theme-card-muted rounded-[24px] px-5 py-8 text-center">
        <Brain size={32} className="mx-auto mb-3 text-[var(--text-muted)]" />
        <h3 className="text-lg font-semibold text-[var(--text-primary)]">No AI Detection Data</h3>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          AI detection has not been run on this assignment yet.
        </p>
      </div>
    );
  }

  const flaggedCount = results.filter((r) => r.ai_probability >= 0.6).length;
  const avgProbability = results.reduce((sum, r) => sum + r.ai_probability, 0) / results.length;
  const highRiskCount = results.filter((r) => r.ai_probability >= 0.8).length;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="theme-card-muted rounded-[22px] px-4 py-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
            Files Analyzed
          </div>
          <div className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">
            {results.length}
          </div>
        </div>

        <div className="theme-card-muted rounded-[22px] px-4 py-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
            AI-Flagged
          </div>
          <div className="mt-2 text-2xl font-semibold text-orange-600">
            {flaggedCount}
          </div>
        </div>

        <div className="theme-card-muted rounded-[22px] px-4 py-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
            Avg AI Score
          </div>
          <div className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">
            {Math.round(avgProbability * 100)}%
          </div>
        </div>
      </div>

      {highRiskCount > 0 && (
        <div className="rounded-[20px] border border-red-500/20 bg-red-500/[0.08] px-4 py-4">
          <div className="flex items-center gap-2 text-red-600">
            <AlertTriangle size={16} />
            <span className="text-sm font-semibold">
              {highRiskCount} file{highRiskCount === 1 ? '' : 's'} with very high AI probability (≥80%)
            </span>
          </div>
        </div>
      )}

      <div className="space-y-3">
        <div className="text-sm font-semibold text-[var(--text-primary)]">AI Detection Results by File</div>
        {results
          .sort((a, b) => b.ai_probability - a.ai_probability)
          .map((result, idx) => (
            <AIDetectionResultRow key={idx} result={result} />
          ))}
      </div>
    </div>
  );
}

function AIDetectionResultRow({ result }) {
  const getTone = (prob) => {
    if (prob >= 0.8) return 'border-red-500/20 bg-red-500/[0.08]';
    if (prob >= 0.6) return 'border-orange-500/20 bg-orange-500/[0.08]';
    if (prob >= 0.4) return 'border-yellow-500/20 bg-yellow-500/[0.08]';
    return 'border-[color:var(--border)] bg-[var(--surface)]';
  };

  const getColor = (prob) => {
    if (prob >= 0.8) return 'text-red-600';
    if (prob >= 0.6) return 'text-orange-600';
    if (prob >= 0.4) return 'text-yellow-600';
    return 'text-[var(--text-secondary)]';
  };

  return (
    <div className={`theme-card rounded-[22px] px-4 py-4 ${getTone(result.ai_probability)}`}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <FileCode size={14} className="text-[var(--text-muted)]" />
            <span className="font-medium text-[var(--text-primary)] break-all">
              {result.file_name || result.file_a || 'Unknown'}
            </span>
          </div>
          {result.indicators && result.indicators.length > 0 && (
            <div className="mt-2 text-xs text-[var(--text-secondary)]">
              {result.indicators[0]}
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right">
            <div className={`text-xl font-bold ${getColor(result.ai_probability)}`}>
              {Math.round(result.ai_probability * 100)}%
            </div>
            <div className="text-[10px] text-[var(--text-muted)]">
              {Math.round(result.confidence * 100)}% confidence
            </div>
          </div>
          <div className="h-12 w-12 rounded-full border-4 border-[color:var(--border)] flex items-center justify-center">
            <Sparkles size={16} className={getColor(result.ai_probability)} />
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-[color:var(--border)]">
        <div
          className={`h-full rounded-full transition-all ${
            result.ai_probability >= 0.8
              ? 'bg-red-500'
              : result.ai_probability >= 0.6
              ? 'bg-orange-500'
              : result.ai_probability >= 0.4
              ? 'bg-yellow-500'
              : 'bg-emerald-500'
          }`}
          style={{ width: `${result.ai_probability * 100}%` }}
        />
      </div>
    </div>
  );
}

export function AIDetectionSignals({ signals = {} }) {
  const signalLabels = {
    perplexity: 'Perplexity Score',
    burstiness: 'Burstiness Analysis',
    stylometry: 'Stylometric Patterns',
    pattern_repetition: 'Pattern Repetition',
  };

  const signalDescriptions = {
    perplexity: 'Measures code predictability - lower entropy suggests AI generation',
    burstiness: 'Analyzes variation in code complexity - uniform patterns suggest AI',
    stylometry: 'Examines writing style - formal comments and generic names are indicators',
    pattern_repetition: 'Detects repeated LLM-specific code patterns',
  };

  return (
    <div className="space-y-4">
      <div className="text-sm font-semibold text-[var(--text-primary)]">Detection Signals</div>
      
      {Object.entries(signals).map(([key, value]) => (
        <div key={key} className="theme-card-muted rounded-[22px] px-4 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="text-sm font-medium text-[var(--text-primary)]">
                {signalLabels[key] || key}
              </div>
              <div className="mt-1 text-xs text-[var(--text-secondary)]">
                {signalDescriptions[key] || 'Signal analysis'}
              </div>
            </div>
            <div className="text-right">
              <div className="text-lg font-bold text-[var(--text-primary)]">
                {Math.round(value * 100)}%
              </div>
              <div className="text-[10px] text-[var(--text-muted)]">AI indicator strength</div>
            </div>
          </div>
          
          {/* Signal strength bar */}
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[color:var(--border)]">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-600 to-indigo-600"
              style={{ width: `${value * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
