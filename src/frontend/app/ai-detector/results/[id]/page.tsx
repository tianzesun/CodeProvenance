// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import axios from 'axios';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  Download,
  FileCode2,
  Loader2,
  Printer,
  ShieldAlert,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

const API = '';

function formatPercent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function getTone(score) {
  if (score >= 0.7) return 'border-red-200 bg-red-50 text-red-700';
  if (score >= 0.45) return 'border-amber-200 bg-amber-50 text-amber-700';
  return 'border-emerald-200 bg-emerald-50 text-emerald-700';
}

function getCreatedAt(value) {
  if (!value) return 'Unknown time';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

export default function AIDetectorReportPage() {
  const { id } = useParams();
  const router = useRouter();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get(`${API}/api/job/${id}`)
      .then((res) => {
        if (res.data?.job_type !== 'ai_detector') {
          router.replace(`/results/${id}`);
          return;
        }
        setJob(res.data);
        setError('');
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load AI Detector report.');
      })
      .finally(() => setLoading(false));
  }, [id, router]);

  const ai = job?.ai_detection || {};
  const submissions = useMemo(() => ai.submissions || [], [ai.submissions]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex min-h-[60vh] items-center justify-center gap-3 text-slate-500">
          <Loader2 size={18} className="animate-spin" />
          Loading AI Detector report...
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            {error}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <style jsx global>{`
        @media print {
          .no-print {
            display: none !important;
          }
          aside,
          nav,
          button {
            display: none !important;
          }
          body {
            background: white !important;
          }
        }
      `}</style>
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="space-y-8">
          <section className="theme-card-strong rounded-[30px] overflow-hidden">
            <div className="theme-section-line px-6 py-5 lg:px-7">
              <Link href="/ai-detector" className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-blue-600">
                <ArrowLeft size={15} />
                AI Detector
              </Link>
              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">
                    <Bot size={13} />
                    AI Detector Report
                  </div>
                  <h1 className="font-display mt-4 text-3xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-4xl">
                    {job.assignment_name || 'AI Generated Code Review'}
                  </h1>
                  <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">
                    {job.course_name || 'Course'} · {getCreatedAt(job.created_at)} · {job.file_count || submissions.length} file{(job.file_count || submissions.length) === 1 ? '' : 's'}
                  </p>
                </div>
                <div className="no-print flex flex-wrap items-center gap-3">
                  <a
                    href={`${API}/report/${id}/ai-originality-pdf`}
                    className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    <Download size={16} />
                    Download PDF
                  </a>
                  <button
                    type="button"
                    onClick={() => window.print()}
                    className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    <Printer size={16} />
                    Print
                  </button>
                  <div className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm font-semibold ${getTone(ai.highest_score || 0)}`}>
                    <ShieldAlert size={16} />
                    Highest signal {formatPercent(ai.highest_score)}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-4">
            <Metric label="Files" value={ai.total_files || 0} />
            <Metric label="Flagged" value={ai.flagged_count || 0} />
            <Metric label="Highest AI Probability" value={formatPercent(ai.highest_score)} />
            <Metric label="Average" value={formatPercent(ai.average_score)} />
          </section>

          <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <div className="border-b border-slate-100 px-5 py-4">
              <div className="text-sm font-semibold text-slate-900">Submission Evidence</div>
              <div className="mt-1 text-xs text-slate-500">AI results are review signals, not standalone misconduct findings.</div>
            </div>
            <div className="divide-y divide-slate-100">
              {submissions.map((entry) => (
                <div key={entry.name} className="grid gap-5 px-5 py-5 xl:grid-cols-[1.1fr_0.9fr]">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <FileCode2 size={16} className="text-slate-400" />
                      <div className="font-medium text-slate-900">{entry.name}</div>
                      <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${getTone(entry.ai_probability)}`}>
                        {entry.status}
                      </span>
                    </div>
                    {entry.indicators?.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {entry.indicators.map((indicator) => (
                          <span key={indicator} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{indicator}</span>
                        ))}
                      </div>
                    )}
                    {entry.error && (
                      <div className="mt-3 text-sm text-red-600">{entry.error}</div>
                    )}
                  </div>

                  <div className="space-y-3">
                    <ScoreBar label="AI probability" value={entry.ai_probability} />
                    <ScoreBar label="Confidence" value={entry.confidence} />
                  </div>
                </div>
              ))}
              {submissions.length === 0 && (
                <div className="px-5 py-8 text-sm text-slate-500">No AI evidence was stored for this report.</div>
              )}
            </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</div>
      <div className="mt-2 flex items-center gap-2 text-2xl font-semibold text-slate-950">
        <CheckCircle2 size={18} className="text-blue-600" />
        {value}
      </div>
    </div>
  );
}

function ScoreBar({ label, value }) {
  const percent = Math.round((Number(value) || 0) * 100);
  return (
    <div>
      <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
        <span>{label}</span>
        <span>{percent}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-blue-600" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
