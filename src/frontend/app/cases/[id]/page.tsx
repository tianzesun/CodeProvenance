// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import {
  ActionButton,
  Card,
  CardHeader,
  
  RiskBadge,
} from '@/components/saas/SaaSPrimitives';
import { assignmentCases, studentACode, studentBCode } from '@/lib/mockIntegrityData';
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Download,
  FileText,
  History,
  MessageSquare,
  SearchCheck,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { useParams } from 'next/navigation';
import { useRef } from 'react';

const flaggedReasons = [
  'Same unusual recursive decomposition',
  'Identical edge-case handling',
  'Renamed variables but same structure',
  'Matching helper function logic',
  'Similarity exceeds course baseline',
];

const contextNotes = [
  'Starter template overlap excluded.',
  'Instructor-provided tests and LMS packaging files ignored.',
  'Common course solution patterns discounted before ranking.',
];

export default function CompareCasePage() {
  const { id } = useParams();
  const currentCase = assignmentCases.find((item) => item.id === id) || assignmentCases[0];
  const [studentA, studentB] = currentCase.students.split(' vs ');
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const syncing = useRef(false);

  const syncScroll = (source, target) => {
    if (syncing.current || !source.current || !target.current) return;
    syncing.current = true;
    target.current.scrollTop = source.current.scrollTop;
    requestAnimationFrame(() => {
      syncing.current = false;
    });
  };

  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <section className="rounded-xl border border-slate-200 bg-white px-5 py-5 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="text-sm font-medium text-slate-500">
                Assignment: {currentCase.course} {currentCase.assignment}
              </div>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
                Instructor Review Case
              </h1>
              <div className="mt-4 grid gap-3 text-sm text-slate-600 sm:grid-cols-2 lg:grid-cols-4">
                <HeaderMetric value="412" label="submissions analyzed" />
                <HeaderMetric value="9" label="cases may need instructor review" />
                <HeaderMetric value="2m 14s" label="analysis completed" />
                <HeaderMetric value={currentCase.rank} label="queue priority" />
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
              Similarity does not by itself imply misconduct. Instructor review is required.
            </div>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <Card className="p-5">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-sm font-semibold text-slate-500">Risk Summary</div>
                <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                  Multiple uncommon similarities were detected.
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
                  This case was flagged based on multiple independent signals. It is recommended
                  for manual review, not treated as a misconduct conclusion.
                </p>
              </div>
              <RiskBadge value={currentCase.risk} label="High Risk" />
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <RiskMetric label="Overall Risk" value="High" tone="red" />
              <RiskMetric label="Confidence" value={currentCase.confidence} tone="slate" />
              <RiskMetric label="Review Time" value="~2 min" tone="blue" />
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
              <ShieldCheck size={17} className="text-blue-600" />
              Confidence Basis
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Confidence derived from 4 independent signals after starter code and common
              assignment patterns were excluded.
            </p>
            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              {currentCase.reason}
            </div>
          </Card>
        </section>

        <Card>
          <CardHeader
            title="Why This Case Was Flagged"
            description="Plain-language evidence for instructor review."
          />
          <div className="grid gap-3 p-5 md:grid-cols-2">
            {flaggedReasons.map((reason) => (
              <div key={reason} className="flex gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <SearchCheck size={18} className="mt-0.5 shrink-0 text-blue-600" />
                <div className="text-sm font-medium text-slate-800">{reason}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Compare Code"
            description="Matching regions are highlighted. Starter code is greyed out and excluded from the risk summary."
          />
          <div className="grid gap-4 p-5 xl:grid-cols-2">
            <CodePanel
              title={studentA || 'Student A'}
              code={studentACode}
              panelRef={leftRef}
              onScroll={() => syncScroll(leftRef, rightRef)}
            />
            <CodePanel
              title={studentB || 'Student B'}
              code={studentBCode}
              panelRef={rightRef}
              onScroll={() => syncScroll(rightRef, leftRef)}
            />
          </div>
        </Card>

        <section className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader title="Previous History" description="Historical context, not a standalone conclusion." />
            <div className="space-y-3 p-5">
              <EvidenceRow
                icon={History}
                title="Similar to Winter 2025 submission set."
                detail="Prior-term match is structural and excludes starter code."
              />
              <EvidenceRow
                icon={ShieldCheck}
                title="No prior confirmed violation for either student."
                detail="Department record check returned no prior case history."
              />
            </div>
          </Card>

          <Card>
            <CardHeader title="Context Notes" description="False-positive controls applied before ranking." />
            <div className="space-y-3 p-5">
              {contextNotes.map((note) => (
                <EvidenceRow key={note} icon={FileText} title={note} detail="Applied automatically." />
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Decision Actions" description="Keep the review outcome simple and auditable." />
            <div className="space-y-3 p-5">
              <ActionButton icon={CheckCircle2}>Mark for Review</ActionButton>
              <ActionButton variant="secondary" icon={AlertTriangle}>Needs More Evidence</ActionButton>
              <ActionButton variant="secondary" icon={XCircle}>Dismiss</ActionButton>
              <ActionButton variant="secondary" icon={Download}>Export PDF</ActionButton>
            </div>
          </Card>
        </section>

        <Card>
          <CardHeader title="Notes" description="Reviewer notes are kept with the case audit trail." />
          <div className="p-5">
            <label className="block">
              <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
                <MessageSquare size={16} />
                Instructor note
              </span>
              <textarea
                className="min-h-36 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-50"
                defaultValue="TA should verify whether this pair worked in the same tutorial section."
              />
            </label>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}

function HeaderMetric({ value, label }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="text-lg font-semibold text-slate-950">{value}</div>
      <div className="mt-1 leading-5">{label}</div>
    </div>
  );
}

function RiskMetric({ label, value, tone }) {
  const tones = {
    red: 'text-red-700 bg-red-50 border-red-100',
    blue: 'text-blue-700 bg-blue-50 border-blue-100',
    slate: 'text-slate-800 bg-slate-50 border-slate-200',
  };

  return (
    <div className={`rounded-xl border p-4 ${tones[tone]}`}>
      <div className="text-sm font-medium opacity-80">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function CodePanel({ title, code, panelRef, onScroll }) {
  const highlightedLines = new Set([5, 6, 8, 11, 13]);
  const starterLines = new Set([1, 2]);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="text-sm font-semibold text-slate-950">{title}</div>
        <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
          <Clock3 size={14} />
          Synchronized scroll
        </div>
      </div>
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-medium text-slate-500">
        Unrelated code collapsed. Starter code greyed out.
      </div>
      <div ref={panelRef} onScroll={onScroll} className="max-h-[620px] overflow-auto bg-slate-950 py-3 text-sm text-slate-100">
        <pre className="min-w-full font-mono leading-6">
          {code.split('\n').map((line, index) => {
            const lineNumber = index + 1;
            const highlighted = highlightedLines.has(lineNumber);
            const starter = starterLines.has(lineNumber);
            return (
              <div
                key={lineNumber}
                className={`grid grid-cols-[52px_1fr] px-3 ${
                  highlighted ? 'bg-red-500/15 ring-1 ring-inset ring-red-400/30' : ''
                } ${starter ? 'bg-slate-800 text-slate-500' : ''}`}
              >
                <span className="select-none pr-3 text-right text-slate-500">{lineNumber}</span>
                <code className="whitespace-pre">{line || ' '}</code>
              </div>
            );
          })}
        </pre>
      </div>
    </div>
  );
}

function EvidenceRow({ icon: Icon, title, detail }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex gap-3">
        <Icon size={17} className="mt-0.5 shrink-0 text-blue-600" />
        <div>
          <div className="text-sm font-semibold text-slate-950">{title}</div>
          <div className="mt-1 text-sm leading-5 text-slate-500">{detail}</div>
        </div>
      </div>
    </div>
  );
}
