import React, { useEffect, useMemo, useState } from "react"
import { getBenchmarkRun, getBenchmarkRunStdout, getBenchmarkRunStderr } from "@/lib/benchmarkRuns"
import { getBenchmarkResult } from "@/lib/benchmarkResults"
import { getPrimaryArtifactUrl, getArtifactFileUrl } from "@/lib/benchmarkArtifacts"
import { MossReportViewer } from "@/components/benchmark/MossReportViewer"
import { MossPairsTable } from "@/components/benchmark/MossPairsTable"
import { MossSimilarityGraph } from "@/components/benchmark/MossSimilarityGraph"

type TabKey = "report" | "pairs" | "graph" | "artifacts" | "logs"

type RunRecord = {
  run_id: string
  dataset_id: string
  task_id: string
  tool: string
  status: string
  created_at_utc: string
  started_at_utc?: string | null
  finished_at_utc?: string | null
  return_code?: number | null
  output_dir: string
  error?: string | null
}

type ResultSummary = {
  run_id: string
  tool: string
  dataset_id: string
  task_id: string
  status: string
  output_dir: string
  primary_artifact?: string | null
  result_url?: string | null
  top_pairs: Array<{
    left?: string
    right?: string
    score?: number | string | null
    left_percent?: number | null
    right_percent?: number | null
    lines_matched?: number | null
    comparison_path?: string | null
    comparison_url?: string | null
  }>
  raw_artifacts: string[]
  metadata?: Record<string, unknown>
}

type Props = {
  runId: string
}

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ")
}

function StatusBadge({ status }: { status?: string }) {
  const color =
    status === "completed"
      ? "bg-green-100 text-green-800 border-green-200"
      : status === "failed"
        ? "bg-red-100 text-red-800 border-red-200"
        : status === "cancelled"
          ? "bg-gray-100 text-gray-800 border-gray-200"
          : "bg-yellow-100 text-yellow-800 border-yellow-200"

  return (
    <span className={cx("inline-flex rounded border px-2 py-1 text-xs font-medium", color)}>
      {status || "unknown"}
    </span>
  )
}

function SummaryCard({
  label,
  value,
}: {
  label: string
  value: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-medium text-slate-900">{value}</div>
    </div>
  )
}

function Tabs({
  active,
  onChange,
  tabs,
}: {
  active: TabKey
  onChange: (next: TabKey) => void
  tabs: Array<{ key: TabKey; label: string; disabled?: boolean }>
}) {
  return (
    <div
      role="tablist"
      aria-label="Benchmark result sections"
      className="flex flex-wrap gap-2 border-b border-slate-200 pb-3"
    >
      {tabs.map((tab) => (
        <button
          key={tab.key}
          role="tab"
          aria-selected={active === tab.key}
          aria-controls={`panel-${tab.key}`}
          id={`tab-${tab.key}`}
          disabled={tab.disabled}
          onClick={() => onChange(tab.key)}
          className={cx(
            "rounded-lg px-4 py-2 text-sm font-medium transition",
            active === tab.key
              ? "bg-slate-900 text-white"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200",
            tab.disabled && "cursor-not-allowed opacity-50"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

function Panel({
  active,
  tab,
  children,
}: {
  active: TabKey
  tab: TabKey
  children: React.ReactNode
}) {
  if (active !== tab) return null
  return (
    <section
      role="tabpanel"
      id={`panel-${tab}`}
      aria-labelledby={`tab-${tab}`}
      className="rounded-xl border border-slate-200 bg-white p-4"
    >
      {children}
    </section>
  )
}

export default function BenchmarkResultTabbedPage({ runId }: Props) {
  const [run, setRun] = useState<RunRecord | null>(null)
  const [result, setResult] = useState<ResultSummary | null>(null)
  const [stdoutText, setStdoutText] = useState("")
  const [stderrText, setStderrText] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>("report")

  const isTerminal = useMemo(
    () => ["completed", "failed", "cancelled"].includes(run?.status || ""),
    [run?.status]
  )

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const tab = params.get("tab") as TabKey | null
    if (tab && ["report", "pairs", "graph", "artifacts", "logs"].includes(tab)) {
      setActiveTab(tab)
    }
  }, [])

  function updateTab(next: TabKey) {
    setActiveTab(next)
    const url = new URL(window.location.href)
    url.searchParams.set("tab", next)
    window.history.replaceState({}, "", url.toString())
  }

  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout> | null = null

    async function loadRunStatus() {
      try {
        const nextRun = await getBenchmarkRun(runId)
        if (!active) return
        setRun(nextRun)

        if (["running", "queued"].includes(nextRun.status)) {
          timer = setTimeout(loadRunStatus, 2000)
        }
      } catch (err: any) {
        if (!active) return
        setError(err?.message || "Failed to load run status")
      }
    }

    loadRunStatus()

    return () => {
      active = false
      if (timer) clearTimeout(timer)
    }
  }, [runId])

  useEffect(() => {
    let active = true

    async function loadLogs() {
      try {
        const [stdoutRes, stderrRes] = await Promise.all([
          getBenchmarkRunStdout(runId),
          getBenchmarkRunStderr(runId),
        ])
        if (!active) return
        setStdoutText(stdoutRes.stdout || "")
        setStderrText(stderrRes.stderr || "")
      } catch (err: any) {
        if (!active) return
        setError(err?.message || "Failed to load logs")
      }
    }

    loadLogs()
    const interval = setInterval(loadLogs, 3000)

    return () => {
      active = false
      clearInterval(interval)
    }
  }, [runId])

  useEffect(() => {
    let active = true

    async function loadResult() {
      if (!isTerminal) return
      try {
        const nextResult = await getBenchmarkResult(runId)
        if (!active) return
        setResult(nextResult)
      } catch (err: any) {
        if (!active) return
        if (run?.status === "completed") {
          setError(err?.message || "Failed to load benchmark result")
        }
      }
    }

    loadResult()

    return () => {
      active = false
    }
  }, [runId, isTerminal, run?.status])

  const tabs = useMemo(
    () => [
      { key: "report" as TabKey, label: "Report", disabled: !result },
      { key: "pairs" as TabKey, label: "Pairs", disabled: !result },
      { key: "graph" as TabKey, label: "Graph", disabled: !result || result?.tool !== "moss" },
      { key: "artifacts" as TabKey, label: "Artifacts", disabled: !result },
      { key: "logs" as TabKey, label: "Logs", disabled: false },
    ],
    [result]
  )

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Benchmark Result</h1>
          <p className="mt-1 text-sm text-slate-600">
            Review report output, suspicious pairs, graph structure, downloadable artifacts, and logs.
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <SummaryCard label="Run ID" value={<span className="break-all font-mono">{runId}</span>} />
          <SummaryCard label="Status" value={<StatusBadge status={run?.status} />} />
          <SummaryCard label="Tool" value={run?.tool || "—"} />
          <SummaryCard label="Dataset / Task" value={`${run?.dataset_id || "—"} / ${run?.task_id || "—"}`} />
          <SummaryCard label="Created" value={run?.created_at_utc || "—"} />
          <SummaryCard label="Return code" value={run?.return_code ?? "—"} />
        </div>
      </div>

      <Tabs active={activeTab} onChange={updateTab} tabs={tabs} />

      <Panel active={activeTab} tab="report">
        {!result ? (
          <div className="text-sm text-slate-600">Waiting for result summary…</div>
        ) : result.tool === "moss" ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {result.result_url && (
                <a
                  href={result.result_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
                >
                  Open canonical MOSS report
                </a>
              )}
              {result.primary_artifact && (
                <a
                  href={getPrimaryArtifactUrl(runId)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
                >
                  Open primary artifact
                </a>
              )}
            </div>

            <MossReportViewer
              runId={runId}
              localIndexPath={
                typeof result.metadata?.mirrored_index_path === "string"
                  ? result.metadata.mirrored_index_path
                  : null
              }
              reportUrl={
                result.result_url ||
                (typeof result.metadata?.embed_url === "string" ? result.metadata.embed_url : null)
              }
              title={`MOSS Report ${result.dataset_id}/${result.task_id}`}
            />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="text-sm text-slate-600">
              This run produced a non-MOSS result. Use the Artifacts tab to download the main report output.
            </div>

            {result.primary_artifact && (
              <a
                href={getPrimaryArtifactUrl(runId)}
                className="inline-flex rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
              >
                Download primary artifact
              </a>
            )}
          </div>
        )}
      </Panel>

      <Panel active={activeTab} tab="pairs">
        {!result ? (
          <div className="text-sm text-slate-600">Waiting for result summary…</div>
        ) : result.tool === "moss" ? (
          result.top_pairs?.length ? (
            <MossPairsTable runId={runId} rows={result.top_pairs} />
          ) : (
            <div className="text-sm text-slate-600">No parsed MOSS pairs are available.</div>
          )
        ) : result.top_pairs?.length ? (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full border-collapse text-sm">
              <thead className="bg-slate-50">
                <tr className="border-b border-slate-200 text-left">
                  <th className="px-3 py-2 font-medium text-slate-700">Submission A</th>
                  <th className="px-3 py-2 font-medium text-slate-700">Submission B</th>
                  <th className="px-3 py-2 font-medium text-slate-700">Score</th>
                </tr>
              </thead>
              <tbody>
                {result.top_pairs.map((pair, idx) => (
                  <tr key={`${pair.left}-${pair.right}-${idx}`} className="border-b border-slate-100">
                    <td className="px-3 py-2 text-slate-900">{pair.left || "—"}</td>
                    <td className="px-3 py-2 text-slate-900">{pair.right || "—"}</td>
                    <td className="px-3 py-2 text-slate-900">{pair.score ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-slate-600">No normalized similarity pairs are available.</div>
        )}
      </Panel>

      <Panel active={activeTab} tab="graph">
        {!result ? (
          <div className="text-sm text-slate-600">Waiting for result summary…</div>
        ) : result.tool !== "moss" ? (
          <div className="text-sm text-slate-600">Graph view is currently available only for MOSS results.</div>
        ) : (
          <MossSimilarityGraph runId={runId} />
        )}
      </Panel>

      <Panel active={activeTab} tab="artifacts">
        {!result ? (
          <div className="text-sm text-slate-600">Waiting for result summary…</div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {result.primary_artifact && (
                <a
                  href={getPrimaryArtifactUrl(runId)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
                >
                  Open primary artifact
                </a>
              )}
              {result.result_url && (
                <a
                  href={result.result_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex rounded border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
                >
                  Open result URL
                </a>
              )}
            </div>

            {result.raw_artifacts?.length ? (
              <div className="space-y-2">
                {result.raw_artifacts.map((artifactPath) => (
                  <div
                    key={artifactPath}
                    className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2"
                  >
                    <div className="truncate pr-4 font-mono text-xs text-slate-700">
                      {artifactPath}
                    </div>
                    <a
                      href={getArtifactFileUrl(runId, artifactPath)}
                      target="_blank"
                      rel="noreferrer"
                      className="shrink-0 text-sm font-medium text-blue-600 hover:text-blue-800"
                    >
                      Open
                    </a>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-slate-600">No local artifacts were discovered for this run.</div>
            )}
          </div>
        )}
      </Panel>

      <Panel active={activeTab} tab="logs">
        <div className="grid gap-4 xl:grid-cols-2">
          <div>
            <div className="mb-2 text-xs uppercase tracking-wide text-slate-500">stdout</div>
            <pre className="max-h-[700px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
              {stdoutText || "No stdout yet"}
            </pre>
          </div>
          <div>
            <div className="mb-2 text-xs uppercase tracking-wide text-slate-500">stderr</div>
            <pre className="max-h-[700px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
              {stderrText || "No stderr yet"}
            </pre>
          </div>
        </div>
      </Panel>
    </div>
  )
}
