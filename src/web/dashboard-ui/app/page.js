'use client';

import DashboardLayout from '@/components/DashboardLayout';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  ArrowRight,
  ChevronRight,
  FileSearch,
  FolderArchive,
  Loader2,
  Settings2,
  Shield,
  Upload,
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || '';

function formatTimestamp(value) {
  if (!value) {
    return 'Awaiting upload';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function getAssignmentTitle(job) {
  return job.assignment_name || job.course_name || 'Untitled assignment check';
}

function getReferenceLabel(job) {
  if (!job.course_name || job.course_name === job.assignment_name) {
    return '';
  }

  return job.course_name;
}

export default function Home() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 30000);

    return () => clearInterval(interval);
  }, []);

  const fetchJobs = async () => {
    try {
      const res = await axios.get(`${API}/api/jobs`);
      setJobs(res.data.jobs || []);
    } catch {
      setJobs([]);
    }

    setLoading(false);
  };

  const recentJobs = jobs.slice(0, 6);
  const latestCompleted = jobs.find((job) => job.status === 'completed');
  const runningCount = jobs.filter((job) => ['processing', 'analyzing'].includes(job.status)).length;

  return (
    <DashboardLayout>
      <div className="px-4 py-4 lg:px-6 lg:py-6">
        <div className="space-y-6">
          <section className="theme-card-strong theme-section-line relative overflow-hidden rounded-[32px] px-6 py-6 lg:px-8 lg:py-8">
            <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-blue-600/[0.08] blur-3xl" />

            <div className="relative grid gap-6 xl:grid-cols-[1.35fr_0.9fr]">
              <div className="space-y-6">
                <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600">
                  <Shield size={13} />
                  Assignment checker
                </div>

                <div className="space-y-4">
                  <h1 className="font-display max-w-3xl text-4xl font-semibold leading-tight text-[var(--text-primary)] sm:text-5xl">
                    Upload submissions and review the result without dashboard clutter.
                  </h1>
                  <p className="max-w-2xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
                    This workspace is centered on one job: checking a single assignment for suspicious similarity,
                    then opening the flagged result quickly.
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Link
                    href="/upload?mode=individual"
                    className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition"
                  >
                    <Upload size={16} />
                    Upload Files
                  </Link>

                  <Link
                    href="/upload?mode=zip"
                    className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition"
                  >
                    <FolderArchive size={16} />
                    Upload ZIP
                  </Link>

                  {latestCompleted && (
                    <Link
                      href={`/results/${latestCompleted.id}`}
                      className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition"
                    >
                      <FileSearch size={16} />
                      Open Latest Result
                    </Link>
                  )}
                </div>

                <div className="flex flex-wrap gap-3 text-sm">
                  <span className="rounded-full border border-[color:var(--border)] bg-[var(--surface-muted)] px-3 py-1.5 text-[var(--text-secondary)]">
                    {runningCount > 0 ? `${runningCount} check${runningCount === 1 ? '' : 's'} in progress` : 'No checks running'}
                  </span>
                  <span className="rounded-full border border-[color:var(--border)] bg-[var(--surface-muted)] px-3 py-1.5 text-[var(--text-secondary)]">
                    {latestCompleted ? `Latest result ready ${formatTimestamp(latestCompleted.created_at)}` : 'No completed result yet'}
                  </span>
                </div>
              </div>

              <div className="theme-card rounded-[28px] p-5 lg:p-6">
                <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  How it works
                </div>
                <div className="mt-4 space-y-4">
                  <GuideStep
                    index="01"
                    title="Upload the assignment"
                    description="Add individual files or a ZIP archive from the submission set you want to review."
                  />
                  <GuideStep
                    index="02"
                    title="Wait for analysis"
                    description="IntegrityDesk runs the check and keeps polling until the result is ready."
                  />
                  <GuideStep
                    index="03"
                    title="Open flagged pairs"
                    description="Review suspicious matches, then export the supporting report if needed."
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.45fr_0.85fr]">
            <div className="theme-card rounded-[30px] overflow-hidden">
              <div className="theme-section-line px-6 py-5">
                <div className="flex items-end justify-between gap-4">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                      Recent checks
                    </div>
                    <h2 className="font-display mt-2 text-2xl font-semibold text-[var(--text-primary)]">
                      Open the last assignment you checked
                    </h2>
                  </div>

                  <Link href="/upload" className="theme-link inline-flex items-center gap-1 text-sm font-medium">
                    Start new check
                    <ChevronRight size={16} />
                  </Link>
                </div>
              </div>

              {loading ? (
                <div className="space-y-3 px-6 pb-6">
                  {[1, 2, 3, 4].map((item) => (
                    <div key={item} className="grid grid-cols-[1.35fr_100px_140px_120px] gap-3">
                      <div className="h-16 rounded-2xl skeleton" />
                      <div className="h-16 rounded-2xl skeleton" />
                      <div className="h-16 rounded-2xl skeleton" />
                      <div className="h-16 rounded-2xl skeleton" />
                    </div>
                  ))}
                </div>
              ) : recentJobs.length === 0 ? (
                <div className="px-6 pb-6">
                  <div className="theme-card-muted rounded-[24px] px-6 py-12 text-center">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-[var(--surface)] text-[var(--accent-blue)]">
                      <Upload size={22} />
                    </div>
                    <h3 className="mt-4 text-xl font-semibold text-[var(--text-primary)]">No checks yet</h3>
                    <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                      Upload an assignment to start the first similarity check. The latest results will appear here.
                    </p>
                    <Link
                      href="/upload"
                      className="theme-button-primary mt-6 inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold"
                    >
                      <Upload size={16} />
                      Upload Assignment
                    </Link>
                  </div>
                </div>
              ) : (
                <div className="overflow-x-auto px-6 pb-6">
                  <table className="min-w-full border-separate border-spacing-y-3">
                    <thead>
                      <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        <th className="px-4 py-2">Assignment</th>
                        <th className="px-4 py-2 text-center">Files</th>
                        <th className="px-4 py-2">Status</th>
                        <th className="px-4 py-2">Created</th>
                        <th className="px-4 py-2 text-right">Open</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentJobs.map((job) => (
                        <tr key={job.id}>
                          <td className="rounded-l-[22px] border border-[color:var(--border)] border-r-0 bg-[var(--surface-muted)] px-4 py-4">
                            <div>
                              <div className="font-medium text-[var(--text-primary)]">{getAssignmentTitle(job)}</div>
                              {getReferenceLabel(job) && (
                                <div className="mt-1 text-xs text-[var(--text-muted)]">{getReferenceLabel(job)}</div>
                              )}
                            </div>
                          </td>
                          <td className="border border-[color:var(--border)] border-l-0 border-r-0 bg-[var(--surface-muted)] px-4 py-4 text-center text-sm font-medium text-[var(--text-primary)]">
                            {job.file_count || 0}
                          </td>
                          <td className="border border-[color:var(--border)] border-l-0 border-r-0 bg-[var(--surface-muted)] px-4 py-4">
                            <StatusBadge status={job.status} />
                          </td>
                          <td className="border border-[color:var(--border)] border-l-0 border-r-0 bg-[var(--surface-muted)] px-4 py-4 text-sm text-[var(--text-secondary)]">
                            {formatTimestamp(job.created_at)}
                          </td>
                          <td className="rounded-r-[22px] border border-[color:var(--border)] border-l-0 bg-[var(--surface-muted)] px-4 py-4 text-right">
                            {job.status === 'completed' ? (
                              <Link
                                href={`/results/${job.id}`}
                                className="theme-link inline-flex items-center gap-1 text-sm font-medium"
                              >
                                Open
                                <ArrowRight size={15} />
                              </Link>
                            ) : (
                              <span className="inline-flex items-center gap-2 text-sm text-[var(--text-muted)]">
                                <Loader2 size={14} className="animate-spin" />
                                Running
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="space-y-4">
              <ActionCard
                href="/upload?mode=individual"
                icon={Upload}
                title="Upload individual files"
                description="Use this when the submissions are already split into separate source files."
              />
              <ActionCard
                href="/upload?mode=zip"
                icon={FolderArchive}
                title="Upload one ZIP archive"
                description="Use this when the assignment comes as a folder export or submission bundle."
              />
              <ActionCard
                href="/settings"
                icon={Settings2}
                title="Review default threshold"
                description="Adjust the similarity cutoff before you start a new check."
              />
            </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}

const GuideStep = ({ index, title, description }) => (
  <div className="rounded-2xl border border-[color:var(--border)] bg-[var(--surface-muted)] px-4 py-4">
    <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">{index}</div>
    <div className="mt-2 text-base font-semibold text-[var(--text-primary)]">{title}</div>
    <div className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{description}</div>
  </div>
);

const ActionCard = ({ href, icon: Icon, title, description }) => (
  <Link
    href={href}
    className="theme-card group block rounded-[28px] px-5 py-5 transition hover:-translate-y-0.5"
  >
    <div className="flex items-start justify-between gap-4">
      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-600/10 text-blue-600">
        <Icon size={18} />
      </div>
      <ArrowRight size={17} className="text-[var(--text-muted)] transition group-hover:translate-x-0.5" />
    </div>
    <div className="mt-5 text-lg font-semibold text-[var(--text-primary)]">{title}</div>
    <div className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{description}</div>
  </Link>
);

const StatusBadge = ({ status }) => {
  const toneMap = {
    analyzing: 'border-amber-500/20 bg-amber-500/10 text-amber-600',
    completed: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600',
    failed: 'border-red-500/20 bg-red-500/10 text-red-600',
    processing: 'border-blue-600/20 bg-blue-600/10 text-blue-600',
  };

  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${toneMap[status] || toneMap.processing}`}>
      {status}
    </span>
  );
};
