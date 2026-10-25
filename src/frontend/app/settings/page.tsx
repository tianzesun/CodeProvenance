// @ts-nocheck — TODO: add proper types (tracked in types/api.ts). Kept on purpose: this page reads
// ~60 loosely typed settings keys, so removing it needs the real `Settings` type from types/api.ts.

'use client';

import React, { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '@/lib/apiClient';
import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { PageHeader } from '@/components/saas/SaaSPrimitives';
import {
  AlertTriangle,
  Bot,
  ChevronDown,
  ExternalLink,
  FolderTree,
  Loader2,
  RefreshCw,
  Save,
  Shield,
  Target,
  Zap,
  Brain,
  Workflow,
  Server,
  Activity,
  Layers,
  XCircle,
  CheckCircle,
  Send,
} from 'lucide-react';

type Settings = Record<string, unknown> & {
  professor_profile?: Record<string, unknown>;
  professor_profile_catalog?: Record<string, unknown>;
  applied_professor_profile?: Record<string, unknown>;
  default_threshold?: number;
  source_scan_sites?: string[];
  source_scan_enabled?: boolean;
  webhook_url?: string;
  notify_email_on_finish?: boolean;
};

interface WeightGovernanceState {
  needs_validation: boolean;
  changed_engines: string[];
  evidence: Record<string, unknown>;
  warnings: string[];
}

interface ValidationResult {
  issues: string[];
  weight_governance?: WeightGovernanceState;
}

// ─── Types ─────────────────────────────────────────────────────────────────────

// ─── Helpers ───────────────────────────────────────────────────────────────────

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

/** Generic, status-keyed text; a correlation id is appended when the backend sends one. */
function describeError(error: unknown, fallback: string): string {
  const response = (error as { response?: { status?: unknown; headers?: unknown } } | null)?.response;
  const status = typeof response?.status === 'number' ? response.status : undefined;
  const headers = (response?.headers ?? {}) as Record<string, unknown>;
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find(
    (value): value is string => typeof value === 'string' && value.length > 0
  );

  let message = fallback;
  // The server validates every setting and names each invalid field.
  const fields = (error as { response?: { data?: { detail?: { fields?: Record<string, string> } } } })?.response?.data?.detail?.fields;
  if (status === 400 && fields && typeof fields === 'object') {
    const problems = Object.entries(fields).map(
      ([key, problem]) => `${NUMBER_RULES[key]?.label ?? key.replace(/_/g, ' ')} ${problem}`,
    );
    if (problems.length) message = `Not saved. ${problems.join('; ')}.`;
  } else if (status === 401) {
    message = 'Your session has expired. Please sign in again.';
  } else if (status === 403) {
    message = 'You don’t have permission to change these settings.';
  } else if (status === 409) {
    message = 'The settings were changed elsewhere. Reload the page and try again.';
  } else if (status === 429) {
    message = 'Too many requests. Please wait a moment and try again.';
  }

  return reference ? `${message} (Reference: ${reference})` : message;
}

/** Credentials. They are only ever sent when the admin typed a new value (see buildPayload). */
const SECRET_KEYS = [
  'openai_api_key',
  'anthropic_api_key',
  'moss_user_id',
  'email_password',
  'sendgrid_api_key',
];

const PLAIN_KEYS = [
  'default_threshold',
  'openai_base_url',
  'openai_model',
  'anthropic_model',
  'llm_provider',
  'llm_fallback_provider',
  'llm_model_overrides',
  'llm_base_urls',
  'embedding_runtime',
  'embedding_model',
  'embedding_server_url',
  'embedding_server_host',
  'embedding_server_port',
  'embedding_device',
  'embedding_batch_size',
  'batch_size',
  'max_file_size_mb',
  'max_files_per_job',
  'email_backend',
  'email_host',
  'email_port',
  'email_user',
  'email_from',
  'email_use_tls',
  'notify_email_on_finish',
];

// Guard rails against typos and "0" (an empty number box used to be saved as 0). The server
// remains the authority on what is actually allowed.
const NUMBER_RULES: Record<string, { min: number; max: number; label: string }> = {
  max_file_size_mb: { min: 1, max: 4096, label: 'Max file size' },
  max_files_per_job: { min: 2, max: 100000, label: 'Max files per job' },
  batch_size: { min: 1, max: 10000, label: 'Processing batch size' },
  embedding_batch_size: { min: 1, max: 4096, label: 'Embedding batch size' },
  embedding_server_port: { min: 1, max: 65535, label: 'Embedding server port' },
  email_port: { min: 1, max: 65535, label: 'SMTP port' },
};

const FIELD_TABS: Record<string, string> = {
  default_threshold: 'detection',
  max_file_size_mb: 'detection',
  max_files_per_job: 'detection',
  batch_size: 'detection',
  source_scan_sites: 'intelligence',
  llm_base_urls: 'intelligence',
  webhook_url: 'system',
  email_from: 'system',
  email_host: 'system',
  email_port: 'system',
  embedding_server_url: 'system',
  embedding_server_port: 'system',
  embedding_batch_size: 'system',
};

const MAX_SOURCE_URLS = 100;
const FALLBACK_THRESHOLD = 0.75; // the "balanced" preset; was 0.82, which matched no preset

// Which accordion holds each validated field. A section that is collapsed hides its errors, so a
// failed save opens every section that contains one.
const FIELD_ACCORDIONS: Record<string, string> = {
  max_file_size_mb: 'systemLimits',
  max_files_per_job: 'systemLimits',
  batch_size: 'systemLimits',
  source_scan_sites: 'publicSources',
  webhook_url: 'webhooks',
  email_from: 'emailDelivery',
  email_host: 'emailDelivery',
  email_port: 'emailDelivery',
  embedding_server_url: 'embeddingAdvanced',
  embedding_server_port: 'embeddingAdvanced',
  embedding_batch_size: 'embeddingAdvanced',
};

function tabForField(key: string): string | undefined {
  return FIELD_TABS[key] ?? FIELD_TABS[key.split(':')[0]];
}

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return (url.protocol === 'http:' || url.protocol === 'https:') && Boolean(url.hostname);
  } catch {
    return false;
  }
}

/** One URL per line. Commas are NOT separators: they are valid inside URLs (query strings). */
function parseSourceUrls(text: string): string[] {
  const seen = new Set<string>();
  const urls: string[] = [];
  for (const line of text.split(/\r?\n/)) {
    const url = line.trim();
    if (url && !seen.has(url)) {
      seen.add(url);
      urls.push(url);
    }
  }
  return urls;
}

/** Only http(s) links from the server-provided provider catalog are rendered as links. */
function safeHref(value: unknown): string | undefined {
  return typeof value === 'string' && isHttpUrl(value) ? value : undefined;
}

function formatPct(value: unknown): string {
  const n = Number(value);
  return value === null || value === undefined || value === '' || Number.isNaN(n) ? '—' : `${Math.round(n * 100)}%`;
}

/** Locale date-time, or '' when the server sent nothing usable (never "Invalid Date"). */
function formatDateTime(value: unknown): string {
  if (typeof value !== 'string' && typeof value !== 'number') return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('en-CA');
}

function checkedSuffix(value: unknown): string {
  const text = formatDateTime(value);
  return text ? `, last checked ${text}` : '';
}

function validateSettings(
  settings: Settings | null,
  webhookUrl: string,
  sourceUrls: string[],
): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!settings) return errors;

  const threshold = settings.default_threshold;
  if (threshold !== undefined && (typeof threshold !== 'number' || Number.isNaN(threshold) || threshold < 0 || threshold > 1)) {
    errors.default_threshold = 'The threshold must be between 0% and 100%.';
  }

  for (const [key, rule] of Object.entries(NUMBER_RULES)) {
    const value = (settings as Record<string, unknown>)[key];
    if (value === undefined) continue;
    if (value === '' || typeof value !== 'number' || Number.isNaN(value)) {
      errors[key] = `${rule.label}: enter a number.`;
    } else if (value < rule.min || value > rule.max) {
      errors[key] = `${rule.label} must be between ${rule.min.toLocaleString('en-CA')} and ${rule.max.toLocaleString('en-CA')}.`;
    }
  }

  if (webhookUrl.trim() && !/^https:\/\//i.test(webhookUrl.trim())) {
    errors.webhook_url = 'Enter a full https URL, for example https://example.com/webhook.';
  }
  const embeddingUrl = String(settings.embedding_server_url || '').trim();
  if (embeddingUrl && !isHttpUrl(embeddingUrl)) {
    errors.embedding_server_url = 'Enter a full http(s) URL, for example http://127.0.0.1:8001/v1.';
  }
  const baseUrls = (settings.llm_base_urls || {}) as Record<string, string>;
  for (const [provider, url] of Object.entries(baseUrls)) {
    if (url && url.trim() && !isHttpUrl(url.trim())) {
      errors[`llm_base_urls:${provider}`] = 'Enter a full http(s) URL.';
    }
  }

  const from = String(settings.email_from || '').trim();
  if (from && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(from)) {
    errors.email_from = 'Enter a valid email address.';
  }
  if (settings.email_backend === 'smtp' && !String(settings.email_host || '').trim()) {
    errors.email_host = 'The SMTP host is required for the SMTP backend.';
  }

  if (settings.source_scan_enabled) {
    const badIndex = sourceUrls.findIndex((url) => !isHttpUrl(url));
    if (sourceUrls.length > MAX_SOURCE_URLS) {
      errors.source_scan_sites = `Too many sources (limit ${MAX_SOURCE_URLS}).`;
    } else if (badIndex !== -1) {
      errors.source_scan_sites = `Entry ${badIndex + 1} isn’t a valid http(s) URL: ${sourceUrls[badIndex].slice(0, 80)}`;
    }
  }

  return errors;
}

/**
 * What a save sends. Credentials are included only when the admin typed a new value (blank means
 * "keep the stored one") or removed the saved one (sent as null); everything else is sent as shown. The page used to send every secret
 * field it held on every save.
 */
function buildPayload(
  s: Settings,
  webhookUrl: string,
  sourceUrls: string[],
  edited: Record<string, boolean>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    professor_profile: { ...DEFAULT_PROFILE, ...(s.professor_profile || {}) },
    webhook_url: webhookUrl.trim(),
    source_scan_enabled: Boolean(s.source_scan_enabled),
    source_scan_sites: sourceUrls,
  };

  for (const key of PLAIN_KEYS) {
    const value = (s as Record<string, unknown>)[key];
    if (value !== undefined) payload[key] = value;
  }

  for (const key of SECRET_KEYS) {
    const value = (s as Record<string, unknown>)[key];
    if (edited[key] && value === null) {
      payload[key] = null;
    } else if (edited[key] && typeof value === 'string' && value.trim()) {
      payload[key] = value.trim();
    }
  }

  if (edited.llm_api_keys) {
    const keys: Record<string, string | null> = {};
    for (const [provider, value] of Object.entries((s.llm_api_keys || {}) as Record<string, unknown>)) {
      if (value === null) keys[provider] = null;
      else if (typeof value === 'string' && value.trim()) keys[provider] = value.trim();
    }
    if (Object.keys(keys).length > 0) payload.llm_api_keys = keys;
  }

  return payload;
}

const DEFAULT_PROFILE = {
  assignment_type: 'auto_detect',
  sensitivity: 'balanced',
  starter_code_handling: 'student_written_only',
  previous_term_matching: 'off',
  ai_rewrite_detection: 'balanced',
  result_volume: 'top_25',
};

// Sensitivity preset → default similarity cutoff (%) for new jobs.
// Higher = stricter cutoff = fewer flags; lower = flags more pairs.
const SENSITIVITY_THRESHOLDS: Record<string, number> = {
  conservative: 0.84,
  balanced: 0.75,
  strict: 0.64,
};

// 4 main categories - each shows all sections on one page.
// `accent` colours the sliding tab pill so the category you are in is obvious.
const MAIN_TABS = [
  {
    id: 'detection',
    label: 'Detection Settings',
    icon: FolderTree,
    accent: '#2563eb',
    description:
      'Keep the default profile for everyday use. IntegrityDesk detects assignment shape, calibrates thresholds, and suppresses common false positives automatically.',
  },
  {
    id: 'intelligence',
    label: 'AI & Evidence',
    icon: Brain,
    accent: '#7c3aed',
    description:
      'Configure AI-generated code detection, embedding models, and the evidence sources used to support each finding.',
  },
  {
    id: 'workflow',
    label: 'Review & Workflow',
    icon: Workflow,
    accent: '#059669',
    description:
      'Set how aggressively submissions are flagged, how starter code and prior terms are handled, and how much review load to surface.',
  },
  {
    id: 'system',
    label: 'System Settings',
    icon: Server,
    accent: '#d97706',
    description:
      'Manage notifications, email delivery, service health and embedding resources for this workspace.',
  },
];

const SENSITIVITY_PRESETS = [
  { id: 'strict', label: 'Strict', hint: 'Flags more pairs, good for early triage' },
  { id: 'balanced', label: 'Balanced', hint: 'Recommended for most courses' },
  { id: 'conservative', label: 'Conservative', hint: 'Fewer flags, for formal cases' },
] as const;

/** One-click starting points for the Review & Workflow choices; each stays editable afterwards. */
const QUICK_SETUPS = [
  {
    id: 'intro',
    label: 'Intro course',
    hint: 'Lots of starter code, assignments reused each term',
    sensitivity: 'balanced',
    profile: { starter_code_handling: 'student_written_only', previous_term_matching: 'same_course_only', ai_rewrite_detection: 'balanced', result_volume: 'top_25' },
  },
  {
    id: 'upper',
    label: 'Upper-year course',
    hint: 'Open-ended work, fewer but stronger flags',
    sensitivity: 'conservative',
    profile: { starter_code_handling: 'ignore_starter_code', previous_term_matching: 'off', ai_rewrite_detection: 'balanced', result_volume: 'top_10' },
  },
  {
    id: 'triage',
    label: 'Early triage',
    hint: 'Cast a wide net, then review',
    sensitivity: 'strict',
    profile: { starter_code_handling: 'student_written_only', previous_term_matching: 'all_historical_courses', ai_rewrite_detection: 'balanced', result_volume: 'top_50' },
  },
  {
    id: 'similarity',
    label: 'Similarity only',
    hint: 'No AI-authorship scores, no past terms',
    sensitivity: 'balanced',
    profile: { starter_code_handling: 'student_written_only', previous_term_matching: 'off', ai_rewrite_detection: 'off', result_volume: 'top_25' },
  },
] as const;

// Calibration findings from the last read-only benchmark run.
const CALIB_METRIC_LABELS: Record<string, string> = {
  f1: 'F1',
  auc_roc: 'AUC',
  optimal_threshold: 'Best threshold',
  accuracy: 'Accuracy',
  precision: 'Precision',
  recall: 'Recall',
  total_pairs: 'Pairs',
};
const formatCalibMetric = (metric: string, value: number): string =>
  metric === 'total_pairs' ? String(Math.round(value)) : value.toFixed(2);

// Weight-governance audit trail (who changed what, against which proof).
interface WeightAuditEntry {
  id: string;
  action: string;
  actor_user_id?: string;
  evidence?: Record<string, unknown>;
  allowed?: boolean;
  note?: string;
  created_at?: string;
}
const AUDIT_ACTION_LABELS: Record<string, string> = {
  weights_updated: 'Weights updated',
  evidence_attached: 'Evidence attached',
  reverted_to_defaults: 'Reverted to defaults',
};

// Shapes mirror GET /api/system/status.
interface ServiceStatusEntry {
  status: string;
  label: string;
  detail?: string;
  latency_ms?: number;
  verified?: boolean;
  provider?: string;
  base_url?: string;
  model?: string;
  models_available?: number;
  default_provider?: string;
  providers?: ServiceStatusEntry[];
}
interface SystemStatusPayload {
  checked_at: string;
  status: string;
  services: Record<string, ServiceStatusEntry>;
}

// Shapes mirror GET /api/jobs/queue.
interface QueueWorkerTask {
  task_id?: string;
  job_id?: string;
  task: string;
  running_seconds?: number;
}
interface QueueWorker {
  name: string;
  active: QueueWorkerTask[];
  reserved: number;
}
interface QueueJob {
  id: string;
  name: string;
  status: string;
  created_at?: string;
  age_seconds?: number;
}
interface QueuePayload {
  db_counts: Record<string, number>;
  workers: QueueWorker[];
  celery_error?: string;
  active_jobs: QueueJob[];
  checked_at: string;
}

// A missing array or object in either payload used to throw during render and blank the whole page.
function normalizeStatus(raw: unknown): SystemStatusPayload | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Partial<SystemStatusPayload>;
  return {
    checked_at: r.checked_at ?? '',
    status: r.status ?? 'unknown',
    services: r.services && typeof r.services === 'object' ? r.services : {},
  };
}

function normalizeQueue(raw: unknown): QueuePayload | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Partial<QueuePayload>;
  return {
    db_counts: r.db_counts && typeof r.db_counts === 'object' ? r.db_counts : {},
    workers: Array.isArray(r.workers)
      ? r.workers.map((worker) => ({
          ...worker,
          active: Array.isArray(worker?.active) ? worker.active : [],
          reserved: Number(worker?.reserved) || 0,
        }))
      : [],
    celery_error: r.celery_error,
    active_jobs: Array.isArray(r.active_jobs) ? r.active_jobs : [],
    checked_at: r.checked_at ?? '',
  };
}

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [activeTab, setActiveTab] = useState<string>('detection');
  const [webhookUrl, setWebhookUrl] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [validationLoading, setValidationLoading] = useState<boolean>(false);

  // Calibration findings from the last read-only benchmark run. Shown under
  // the Run Calibration button; cleared on each new run.
  const [calibResult, setCalibResult] = useState<Record<string, number> | null>(null);

  // Weight-governance evidence form: the Configuration Check warns until a
  // default weight change names its validation run, benchmark dataset and
  // metric snapshot. This records that evidence so the warnings can clear.
  const [govForm, setGovForm] = useState({ validation_run_id: '', benchmark_dataset_id: '', metric_snapshot: '' });
  const [govSaving, setGovSaving] = useState<boolean>(false);
  const [govMessage, setGovMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [govConfirmRevert, setGovConfirmRevert] = useState<boolean>(false);

  // Weight-governance audit trail (who changed what, against which proof).
  const [auditEntries, setAuditEntries] = useState<WeightAuditEntry[]>([]);
  const loadWeightAudit = async (): Promise<void> => {
    try {
      const res = await apiClient.get('/api/settings/weight-audit');
      const entries = ((res.data || {}) as { entries?: unknown }).entries;
      setAuditEntries(Array.isArray(entries) ? (entries as WeightAuditEntry[]) : []);
    } catch {
      setAuditEntries([]);
    }
  };
  useEffect(() => {
    if (validationResult?.weight_governance?.needs_validation) void loadWeightAudit();
  }, [validationResult?.weight_governance?.needs_validation]);

  const govEvidenceText = (value: unknown): string => {
    if (typeof value === 'string') return value;
    if (value === null || value === undefined) return '';
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  };
  const [calibrating, setCalibrating] = useState<boolean>(false);
  const [showCalibrateConfirm, setShowCalibrateConfirm] = useState<boolean>(false);
  const [testingEmail, setTestingEmail] = useState<boolean>(false);
  const [testEmailResult, setTestEmailResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [sourceUrlsText, setSourceUrlsText] = useState('');
  const [editedSecrets, setEditedSecrets] = useState<Record<string, boolean>>({});
  const [savedSnapshot, setSavedSnapshot] = useState('');
  const serverSettingsRef = useRef<Settings | null>(null);
  const noticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sliding active-tab indicator. Measured from the tab list so the pill stays
  // aligned on wrap, resize, and font load.
  const tabListRef = useRef<HTMLDivElement | null>(null);
  const tabButtonRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [indicator, setIndicator] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  const settingsReady = Boolean(settings);

  // offsetLeft/offsetTop are relative to the tab list (it is `relative`), so the pill also lands on the
  // right row when the tabs wrap on a narrow screen. The old version only measured x and width.
  const syncIndicator = useCallback(() => {
    const button = tabButtonRefs.current[activeTab];
    if (!button || button.offsetWidth === 0) return;
    const next = { x: button.offsetLeft, y: button.offsetTop, width: button.offsetWidth, height: button.offsetHeight };
    setIndicator((prev) =>
      prev && prev.x === next.x && prev.y === next.y && prev.width === next.width && prev.height === next.height
        ? prev
        : next,
    );
  }, [activeTab]);

  // The tab bar only mounts once the settings request resolves, so `settingsReady` re-runs these effects
  // at that moment; without it the first measurement was missed.
  useLayoutEffect(() => {
    syncIndicator();
    // Re-measure once webfonts settle, since a font swap reflows the labels.
    if (typeof document !== 'undefined' && document.fonts?.ready) {
      let cancelled = false;
      document.fonts.ready.then(() => {
        if (!cancelled) syncIndicator();
      });
      return () => {
        cancelled = true;
      };
    }
  }, [syncIndicator, settingsReady]);

  // Fires on resize, wrap and sidebar collapse, not just window resizes.
  useEffect(() => {
    const list = tabListRef.current;
    if (!list || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => syncIndicator());
    observer.observe(list);
    return () => observer.disconnect();
  }, [syncIndicator, settingsReady]);

  const [accordions, setAccordions] = useState<Record<string, boolean>>({
    systemLimits: true,
    publicSources: true,
    legacyTools: false,
    webhooks: true,
    embeddingAdvanced: false,
    configValidation: false,
    starterCodeHandling: false,
    previousTermMatching: false,
    aiRewriteDetection: false,
    reviewQueueSize: false,
    emailDelivery: true,
  });

  /** Replace the page state with what the server holds and take a new "saved" baseline. */
  const applyLoaded = useCallback((data: Settings) => {
    serverSettingsRef.current = data;
    const urls = Array.isArray(data.source_scan_sites) ? data.source_scan_sites : [];
    setSettings(data);
    setWebhookUrl(data.webhook_url || '');
    setSourceUrlsText(urls.join('\n'));
    setEditedSecrets({});
    setSavedSnapshot(JSON.stringify(buildPayload(data, data.webhook_url || '', parseSourceUrls(urls.join('\n')), {})));
  }, []);

  // Keyed on the user's id, not the whole `user` object. An auth refresh creates a new object, and
  // this effect used to re-run and overwrite whatever the admin had typed with the server copy.
  const userId = user?.id;

  useEffect(() => {
    if (authLoading || !userId) return;
    const controller = new AbortController();
    setLoadError(null);

    apiClient.get('/api/settings', { signal: controller.signal })
      .then((res) => applyLoaded(res.data))
      .catch((err) => {
        // A failed load used to leave "Loading settings..." on screen forever.
        if (!controller.signal.aborted) setLoadError(describeError(err, 'Failed to load settings.'));
      });

    return () => controller.abort();
  }, [authLoading, userId, reloadKey, applyLoaded]);

  const showSuccess = (message: string, ms = 4000) => {
    setSuccess(message);
    if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
    noticeTimerRef.current = setTimeout(() => setSuccess(null), ms);
  };

  useEffect(() => () => {
    if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
  }, []);

  // Merged with the defaults: a saved profile missing a key left that option with nothing selected.
  const profile = { ...DEFAULT_PROFILE, ...(settings?.professor_profile || {}) } as Record<string, any>;
  const catalog = settings?.professor_profile_catalog || {};
  const applied = settings?.applied_professor_profile || {};
  const activeTabInfo = MAIN_TABS.find((tab) => tab.id === activeTab);

  const sourceUrls = useMemo(() => parseSourceUrls(sourceUrlsText), [sourceUrlsText]);
  const fieldErrors = useMemo(
    () => validateSettings(settings, webhookUrl, sourceUrls),
    [settings, webhookUrl, sourceUrls],
  );
  const errorsByTab = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const key of Object.keys(fieldErrors)) {
      const tab = tabForField(key);
      if (tab) counts[tab] = (counts[tab] || 0) + 1;
    }
    return counts;
  }, [fieldErrors]);
  const dirty = useMemo(
    () => Boolean(settings) && Boolean(savedSnapshot)
      && JSON.stringify(buildPayload(settings as Settings, webhookUrl, sourceUrls, editedSecrets)) !== savedSnapshot,
    [settings, webhookUrl, sourceUrls, editedSecrets, savedSnapshot],
  );
  const errorCount = Object.keys(fieldErrors).length;
  const rawThreshold = Number(settings?.default_threshold ?? FALLBACK_THRESHOLD);
  const threshold = Number.isFinite(rawThreshold) ? rawThreshold : FALLBACK_THRESHOLD;
  const activePreset = SENSITIVITY_PRESETS.find((preset) => Math.abs(threshold - SENSITIVITY_THRESHOLDS[preset.id]) <= 0.005);

  // Leaving or reloading the page with unsaved edits would silently discard them.
  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  const updateSetting = (key: string, value: unknown) => {
    if (SECRET_KEYS.includes(key) || key === 'llm_api_keys') {
      setEditedSecrets((current) => ({ ...current, [key]: true }));
    }
    setSettings((current: Settings | null) => ({ ...(current || {}), [key]: value } as Settings));
  };

  // Number boxes keep an empty value as '' (it used to become 0 through Number('')) and the
  // validation then asks for a number instead of saving 0.
  const updateNumber = (key: string, raw: string) => {
    updateSetting(key, raw.trim() === '' ? '' : Number(raw));
  };

  const numberProps = (key: string) => ({
    min: NUMBER_RULES[key]?.min,
    max: NUMBER_RULES[key]?.max,
    error: fieldErrors[key],
  });

  const updateProfile = (key: string, value: unknown) => {
    setSettings((current: Settings | null) => ({
      ...(current || {}),
      professor_profile: {
        ...DEFAULT_PROFILE,
        ...(current?.professor_profile || {}),
        [key]: value,
      },
    } as Settings));
  };

  // Sends a diagnostic email through the backend's persisted settings. The
  // backend reads what was last saved, so unsaved edits are not used.
  const sendTestEmail = async () => {
    setTestingEmail(true);
    setTestEmailResult(null);
    try {
      const res = await apiClient.post('/api/settings/email/test', {});
      setTestEmailResult({
        ok: Boolean(res.data?.ok),
        message: res.data?.message || 'Test completed.',
      });
    } catch (err: unknown) {
      setTestEmailResult({ ok: false, message: describeError(err, 'The test email could not be sent.') });
    } finally {
      setTestingEmail(false);
    }
  };

  // Changing the sensitivity preset also updates the default cutoff so the
  // threshold slider and the applied-profile summary stay in sync.
  const updateSensitivity = (value: string) => {
    updateProfile('sensitivity', value);
    const preset = SENSITIVITY_THRESHOLDS[value];
    if (preset !== undefined) updateSetting('default_threshold', preset);
  };

  const applyQuickSetup = (setup: (typeof QUICK_SETUPS)[number]) => {
    for (const [key, value] of Object.entries(setup.profile)) updateProfile(key, value);
    updateSensitivity(setup.sensitivity);
  };
  const activeQuickSetup = QUICK_SETUPS.find(
    (setup) =>
      setup.sensitivity === profile.sensitivity &&
      Math.abs(threshold - SENSITIVITY_THRESHOLDS[setup.sensitivity]) <= 0.005 &&
      Object.entries(setup.profile).every(([key, value]) => profile[key] === value),
  );

  // Live provider connection test so the Connected badge reflects a verified
  // API call rather than merely the presence of a stored key.
  const [providerTest, setProviderTest] = useState<Record<string, { testing: boolean; message: string; ok: boolean }>>({});

  // Live service-health overview (database, embedding, LLM, GPU, disk) for
  // the System tab. Shapes mirror GET /api/system/status.
  const [sysStatus, setSysStatus] = useState<SystemStatusPayload | null>(null);
  const [sysLoading, setSysLoading] = useState(false);
  const [sysError, setSysError] = useState<string | null>(null);

  // Job queue monitor (System tab): live counts, worker activity, active
  // jobs with admin kill. Shapes mirror GET /api/jobs/queue.
  const [queueData, setQueueData] = useState<QueuePayload | null>(null);
  const [queueLoading, setQueueLoading] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [killArmed, setKillArmed] = useState<string | null>(null);
  const [killMessage, setKillMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [killAllArmed, setKillAllArmed] = useState<boolean>(false);

  const serviceTone = (status: string): string =>
    status === 'up'
      ? 'border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-emerald-500/10'
      : status === 'down'
        ? 'border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10'
        : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900';
  const serviceDot = (status: string): string =>
    status === 'up' ? 'bg-emerald-500' : status === 'down' ? 'bg-red-500' : 'bg-slate-300 dark:bg-slate-600';
  const serviceWord = (status: string): string =>
    status === 'up' ? 'Up' : status === 'down' ? 'Down' : 'Not configured';

  // Vendor catalog + live model listings. The catalog comes with /api/settings
  // (settings.llm_providers); model lists are fetched per provider so the UI
  // always offers the vendor's newest models instead of a hardcoded list.
  const providers: any[] = Array.isArray((settings as any)?.llm_providers) ? (settings as any).llm_providers : [];
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [modelOptions, setModelOptions] = useState<Record<string, any[]>>({});
  const [modelSource, setModelSource] = useState<Record<string, string>>({});
  const [modelMessage, setModelMessage] = useState<Record<string, string>>({});
  const [modelsLoading, setModelsLoading] = useState<Record<string, boolean>>({});

  const activeProvider = selectedProvider || String((settings as any)?.llm_provider || providers[0]?.key || 'openai');
  const activeSpec = providers.find((p) => p.key === activeProvider) || providers[0] || null;
  const configuredMap: Record<string, boolean> = (settings as any)?.llm_api_keys_configured || {};
  const overridesMap: Record<string, string> = (settings as any)?.llm_model_overrides || {};
  const baseUrlsMap: Record<string, string> = (settings as any)?.llm_base_urls || {};

  // Status-pill truth: keyed vendors are configured once a key is stored;
  // keyless local runtimes (Ollama) need a saved model instead, and any
  // provider that just passed Test Connection reports "Connected".
  const providerStatus = (
    spec: { key: string; requires_key?: boolean } | null,
  ): { configured: boolean; label: string } => {
    if (!spec) return { configured: false, label: 'Not configured' };
    if (providerTest[spec.key]?.ok) return { configured: true, label: 'Connected' };
    if (spec.requires_key) {
      return configuredMap[spec.key]
        ? { configured: true, label: 'Key stored' }
        : { configured: false, label: 'Not configured' };
    }
    return (overridesMap[spec.key] || '').trim()
      ? { configured: true, label: 'Configured' }
      : { configured: false, label: 'Not configured' };
  };
  const activeStatus = providerStatus(activeSpec);

  const loadModels = async (provider: string, refresh = false) => {
    if (!provider) return;
    setModelsLoading((cur) => ({ ...cur, [provider]: true }));
    try {
      const res = await apiClient.get('/api/settings/ai-providers/models', {
        params: { provider, refresh: refresh ? 1 : 0 },
      });
      const body = res.data || {};
      setModelOptions((cur) => ({ ...cur, [provider]: body.models || [] }));
      setModelSource((cur) => ({ ...cur, [provider]: body.source || 'recommended' }));
      setModelMessage((cur) => ({ ...cur, [provider]: body.message || '' }));
    } catch (err) {
      setModelMessage((cur) => ({ ...cur, [provider]: describeError(err, 'Could not load models.') }));
      setModelOptions((cur) => ({ ...cur, [provider]: [] }));
    } finally {
      setModelsLoading((cur) => ({ ...cur, [provider]: false }));
    }
  };

  const setProviderKey = (provider: string, value: string | null) => {
    const keys = { ...((settings as any)?.llm_api_keys || {}), [provider]: value };
    updateSetting('llm_api_keys', keys);
    // Keep the legacy single-vendor fields in sync so old consumers still work.
    if (provider === 'openai') updateSetting('openai_api_key', value);
    if (provider === 'anthropic') updateSetting('anthropic_api_key', value);
  };

  const setProviderModel = (provider: string, value: string) => {
    updateSetting('llm_model_overrides', { ...overridesMap, [provider]: value });
    if (provider === 'openai') updateSetting('openai_model', value);
    if (provider === 'anthropic') updateSetting('anthropic_model', value);
  };

  const setProviderBaseUrl = (provider: string, value: string) => {
    updateSetting('llm_base_urls', { ...baseUrlsMap, [provider]: value });
    if (provider === 'openai') updateSetting('openai_base_url', value);
  };

  const testProvider = async (provider: string) => {
    setProviderTest((current) => ({ ...current, [provider]: { testing: true, message: 'Testing connection\u2026', ok: false } }));
    try {
      const keyMap: Record<string, string> = (settings as any)?.llm_api_keys || {};
      const legacy = provider === 'openai' ? settings?.openai_api_key : settings?.anthropic_api_key;
      const key = String(keyMap[provider] || legacy || '').trim();
      const res = await apiClient.post('/api/settings/ai-provider/test', {
        provider,
        api_key: key || undefined,
      });
      const body = res.data || {};
      setProviderTest((current) => ({
        ...current,
        [provider]: { testing: false, message: body.message || (body.ok ? 'Connected' : 'Failed'), ok: Boolean(body.ok) },
      }));
    } catch (err) {
      setProviderTest((current) => ({
        ...current,
        [provider]: { testing: false, message: describeError(err, 'Connection failed.'), ok: false },
      }));
    }
  };

  // Fetch the vendor's current models whenever the selected provider changes.
  useEffect(() => {
    if (!activeProvider || providers.length === 0) return;
    if (!modelOptions[activeProvider]) void loadModels(activeProvider);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProvider, providers.length]);

  const refreshSystemStatus = async (): Promise<void> => {
    setSysLoading(true);
    setSysError(null);
    try {
      const res = await apiClient.get('/api/system/status');
      setSysStatus(normalizeStatus(res.data));
    } catch (err) {
      setSysError(describeError(err, 'Could not load service status.'));
    } finally {
      setSysLoading(false);
    }
  };

  // Load the service overview whenever the System tab opens — every time,
  // not just the first: provider/default changes made on other tabs (or a
  // previously failed fetch) would otherwise leave a stale tile that
  // disagrees with the saved configuration.
  useEffect(() => {
    if (activeTab === 'system' && !sysLoading) void refreshSystemStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // Background polls are "silent": no spinner flicker every 10 s, and a poll never overlaps a slow one.
  const queueInFlight = useRef(false);
  const refreshQueue = async (options: { silent?: boolean } = {}): Promise<void> => {
    if (options.silent && queueInFlight.current) return;
    queueInFlight.current = true;
    if (!options.silent) {
      setQueueLoading(true);
      setQueueError(null);
    }
    try {
      const res = await apiClient.get('/api/jobs/queue');
      setQueueData(normalizeQueue(res.data));
      setQueueError(null);
    } catch (err) {
      setQueueError(describeError(err, 'Could not load job queue.'));
    } finally {
      queueInFlight.current = false;
      if (!options.silent) setQueueLoading(false);
    }
  };

  // Queue monitor polls while the System tab is open so stuck jobs surface without manual refreshes.
  // It pauses while the browser tab is hidden, and the timer dies with the tab switch.
  useEffect(() => {
    if (activeTab !== 'system') return;
    void refreshQueue();
    const timer = setInterval(() => {
      if (!document.hidden) void refreshQueue({ silent: true });
    }, 10000);
    return () => clearInterval(timer);
  }, [activeTab]);

  const killJob = async (jobId: string): Promise<void> => {
    setKillMessage(null);
    try {
      const res = await apiClient.post(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {});
      const body = (res.data || {}) as { message?: string };
      setKillMessage({
        ok: true,
        text: body.message || 'Cancellation requested.',
      });
      setKillArmed(null);
      await refreshQueue();
    } catch (err) {
      setKillMessage({ ok: false, text: describeError(err, 'Could not cancel job.') });
    }
  };

  const killAllJobs = async (): Promise<void> => {
    setKillMessage(null);
    try {
      const res = await apiClient.post('/api/jobs/cancel-all', {});
      const body = (res.data || {}) as { message?: string; cancelled?: unknown[]; skipped?: unknown[] };
      const extra = Array.isArray(body.skipped) && body.skipped.length > 0 ? ` (${body.skipped.length} skipped)` : '';
      setKillMessage({
        ok: true,
        text: (body.message || 'Bulk cancellation requested.') + extra,
      });
      setKillAllArmed(false);
      await refreshQueue();
    } catch (err) {
      setKillMessage({ ok: false, text: describeError(err, 'Could not cancel jobs.') });
    }
  };

  const queueAgeText = (seconds?: number): string => {
    if (seconds === undefined || seconds === null) return '—';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  };

  const validateConfig = async () => {
    setValidationLoading(true);
    try {
      const res = await apiClient.get('/api/settings/validation');
      setValidationResult(res.data);
      const stored = (res.data as ValidationResult | null)?.weight_governance?.evidence;
      if (stored && Object.keys(stored).length > 0) {
        setGovForm({
          validation_run_id: govEvidenceText(stored.validation_run_id),
          benchmark_dataset_id: govEvidenceText(stored.benchmark_dataset_id),
          metric_snapshot: govEvidenceText(stored.metric_snapshot),
        });
      }
    } catch (err: unknown) {
      setValidationResult({ issues: [describeError(err, 'Failed to validate the configuration.')] });
    } finally {
      setValidationLoading(false);
    }
  };

  const submitGovernanceEvidence = async () => {
    setGovSaving(true);
    setGovMessage(null);
    try {
      const res = await apiClient.post('/api/settings/weight-governance-evidence', {
        validation_run_id: govForm.validation_run_id.trim(),
        benchmark_dataset_id: govForm.benchmark_dataset_id.trim(),
        metric_snapshot: govForm.metric_snapshot.trim(),
      });
      const body = (res.data || {}) as { ok?: boolean; message?: string };
      setGovMessage({
        ok: Boolean(body.ok),
        text: body.message || (body.ok ? 'Evidence recorded.' : 'Evidence recorded with warnings.'),
      });
      await validateConfig();
    } catch (err: unknown) {
      setGovMessage({ ok: false, text: describeError(err, 'Could not save validation evidence.') });
    } finally {
      setGovSaving(false);
    }
  };

  const submitGovernanceAuto = async () => {
    setGovSaving(true);
    setGovMessage(null);
    try {
      const res = await apiClient.post('/api/settings/weight-governance-evidence/auto', {});
      const body = (res.data || {}) as { ok?: boolean; message?: string };
      setGovMessage({
        ok: Boolean(body.ok),
        text: body.message || (body.ok ? 'Benchmark evidence attached.' : 'Benchmark evidence attached with warnings.'),
      });
      await validateConfig();
    } catch (err: unknown) {
      setGovMessage({ ok: false, text: describeError(err, 'Could not attach benchmark evidence. No labeled benchmark runs may exist yet.') });
    } finally {
      setGovSaving(false);
    }
  };

  const submitGovernanceRevert = async () => {
    setGovSaving(true);
    setGovMessage(null);
    try {
      const res = await apiClient.post('/api/settings/weight-governance-revert', {});
      const body = (res.data || {}) as { ok?: boolean; message?: string };
      setGovMessage({
        ok: Boolean(body.ok),
        text: body.message || (body.ok ? 'Reverted to shipped defaults.' : 'Revert did not clear the warnings.'),
      });
      await validateConfig();
    } catch (err: unknown) {
      setGovMessage({ ok: false, text: describeError(err, 'Could not revert weights.') });
    } finally {
      setGovSaving(false);
    }
  };

  const triggerCalibration = async () => {
    // Calibration reloads the settings from the server, which would throw away unsaved edits.
    if (dirty) {
      setShowCalibrateConfirm(false);
      setError('Save or discard your changes before running calibration.');
      return;
    }
    setCalibrating(true);
    setError(null);
    setCalibResult(null);
    try {
      const res = await apiClient.post('/api/settings/calibrate');
      const raw = ((res.data || {}) as Record<string, unknown>).results as Record<string, unknown> | undefined;
      const picked: Record<string, number> = {};
      for (const key of ['f1', 'auc_roc', 'optimal_threshold', 'accuracy', 'precision', 'recall', 'total_pairs']) {
        const value = raw?.[key];
        if (typeof value === 'number' && Number.isFinite(value)) picked[key] = value;
      }
      setCalibResult(picked);
      const current = (settings as unknown as Record<string, unknown>)?.default_threshold;
      const currentText = typeof current === 'number' ? ` (current default ${current})` : '';
      showSuccess(
        `Calibration completed: F1 ${picked.f1?.toFixed(2) ?? '—'} · AUC ${picked.auc_roc?.toFixed(2) ?? '—'} · best threshold ${picked.optimal_threshold?.toFixed(2) ?? '—'}${currentText}. No settings were changed.`,
        8000,
      );
      // Refresh settings after calibration
      const fresh = await apiClient.get('/api/settings');
      applyLoaded(fresh.data);
    } catch (err: unknown) {
      setError(describeError(err, 'Calibration failed.'));
    } finally {
      setCalibrating(false);
      setShowCalibrateConfirm(false);
    }
  };

  const saveSettings = async () => {
    if (!settings || saving || !dirty) return;

    const errorKeys = Object.keys(fieldErrors);
    if (errorKeys.length > 0) {
      const tab = tabForField(errorKeys[0]);
      if (tab) setActiveTab(tab);
      const toOpen = errorKeys.map((key) => FIELD_ACCORDIONS[key]).filter(Boolean);
      if (toOpen.length > 0) {
        setAccordions((prev) => ({ ...prev, ...Object.fromEntries(toOpen.map((id) => [id, true])) }));
      }
      setError(`Fix the ${errorKeys.length} highlighted field${errorKeys.length === 1 ? '' : 's'} before saving.`);
      return;
    }

    setSaving(true);
    setError(null);
    // Remember what default provider was submitted: if the re-read below
    // comes back with a different value, the server silently dropped the
    // change (e.g. an older backend) and the UI must say so loudly instead
    // of displaying the stale selection as if it saved.
    const submittedProvider = String((settings as unknown as Record<string, unknown>)?.llm_provider || '');
    let ignoredProvider = '';

    try {
      try {
        const saveRes = await apiClient.patch('/api/settings', buildPayload(settings, webhookUrl, sourceUrls, editedSecrets));
        ignoredProvider = String(
          ((saveRes.data as unknown as Record<string, unknown>)?.ignored as Record<string, unknown> | undefined)?.llm_provider || '',
        );
      } catch (err: unknown) {
        setError(describeError(err, 'Failed to save settings.'));
        return;
      }

      // The save itself worked. A failed re-read must not be reported as a failed save.
      try {
        const fresh = await apiClient.get('/api/settings');
        applyLoaded(fresh.data);
        const keptProvider = String((fresh.data as unknown as Record<string, unknown>)?.llm_provider || '');
        if (ignoredProvider) {
          setError(`The server refused the default provider value: ${ignoredProvider}`);
        } else if (submittedProvider && keptProvider && keptProvider !== submittedProvider) {
          setError(`The default provider change was not kept by the server (still “${keptProvider}”). Check that the backend is up to date and try again.`);
        } else {
          showSuccess('Settings saved.');
        }
      } catch {
        showSuccess('Settings saved, but the page couldn’t refresh. Reload to see the stored values.', 6000);
      }
      // Any earlier configuration check described the old settings.
      setValidationResult(null);
    } finally {
      setSaving(false);
    }
  };

  const discardChanges = () => {
    if (serverSettingsRef.current) {
      applyLoaded(serverSettingsRef.current);
      setError(null);
    }
  };

  // Ctrl/Cmd+S saves instead of opening the browser's "save page" dialog.
  const saveRef = useRef(saveSettings);
  useEffect(() => {
    saveRef.current = saveSettings;
  });
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        void saveRef.current();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Arrow keys / Home / End move between tabs, as the ARIA tabs pattern expects.
  const onTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = MAIN_TABS.length - 1;
    let next = -1;
    if (event.key === 'ArrowRight') next = index === last ? 0 : index + 1;
    else if (event.key === 'ArrowLeft') next = index === 0 ? last : index - 1;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = last;
    if (next === -1) return;
    event.preventDefault();
    const id = MAIN_TABS[next].id;
    setActiveTab(id);
    tabButtonRefs.current[id]?.focus();
  };

  if (authLoading || !settings) {
    return (
      <DashboardLayout requiredRole="admin">
        {loadError ? (
          <div className="flex h-64 flex-col items-center justify-center gap-4 px-4 py-8 text-center">
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">{loadError}</p>
            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              className="inline-flex h-9 items-center rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              Try again
            </button>
          </div>
        ) : (
          <div role="status" className="flex h-64 items-center justify-center px-4 py-8 text-slate-500 dark:text-slate-400">Loading settings...</div>
        )}
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout requiredRole="admin">
      <div className={`theme-page-container space-y-6 ${dirty ? 'pb-24' : ''}`}>
        {/* Header - title and description follow the active category so the page
            does not keep claiming "Detection Settings" on every tab. */}
        <PageHeader
          eyebrow="Settings"
          title={activeTabInfo?.label ?? 'Settings'}
          description={activeTabInfo?.description ?? ''}
          action={
            <div className="flex flex-wrap items-center gap-2">
              {dirty && (
                <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
                  Unsaved changes
                </span>
              )}
              {dirty && (
                <button
                  type="button"
                  onClick={discardChanges}
                  disabled={saving}
                  className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:hover:bg-slate-900"
                >
                  Discard
                </button>
              )}
              <button
                type="button"
                onClick={saveSettings}
                disabled={saving || !dirty}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                {saving ? 'Saving...' : 'Save changes'}
              </button>
            </div>
          }
          eyebrowStyle="badge"
        />

        {/* Notifications */}
        {error && <Notice tone="red" icon={AlertTriangle}>{error}</Notice>}
        {success && <Notice tone="green" icon={CheckCircle}>{success}</Notice>}

        {/* Main Tab Navigation */}
        <div role="tablist" aria-label="Settings categories" className="relative flex flex-wrap gap-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-2 shadow-sm" ref={tabListRef}>
          {indicator && (
            <span
              aria-hidden="true"
              className="settings-tab-indicator absolute left-0 top-0 rounded-xl shadow-lg transition-[transform,width,height,background-color] duration-300 ease-out motion-reduce:transition-none"
              style={{
                transform: `translate(${indicator.x}px, ${indicator.y}px)`,
                width: indicator.width,
                height: indicator.height,
                backgroundColor: activeTabInfo?.accent ?? '#2563eb',
                boxShadow: `0 10px 24px -12px ${activeTabInfo?.accent ?? '#2563eb'}`,
              }}
            />
          )}
          {MAIN_TABS.map((tab, index) => (
            <button
              key={tab.id}
              type="button"
              ref={(node) => { tabButtonRefs.current[tab.id] = node; }}
              onClick={() => setActiveTab(tab.id)}
              onKeyDown={(event) => onTabKeyDown(event, index)}
              tabIndex={activeTab === tab.id ? 0 : -1}
              role="tab"
              id={`settings-tab-${tab.id}`}
              aria-selected={activeTab === tab.id}
              aria-controls="settings-tabpanel"
              // Until the pill has been measured the active tab paints its own colour; after that
              // the pill slides underneath and the button stays transparent.
              className={`relative inline-flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-colors duration-200 ${activeTab === tab.id
                ? 'text-white'
                : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-900'
                }`}
              style={
                activeTab === tab.id && !indicator
                  ? { backgroundColor: tab.accent, boxShadow: `0 10px 24px -12px ${tab.accent}` }
                  : undefined
              }
            >
              <tab.icon size={16} aria-hidden="true" />
              {tab.label}
              {errorsByTab[tab.id] > 0 && (
                <span
                  className="ml-0.5 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-semibold text-white"
                  title="Fields that need attention"
                >
                  {errorsByTab[tab.id]}
                  <span className="sr-only"> fields need attention</span>
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab Content - All sections shown per category. Keyed on activeTab so
            the entrance animation replays on every category switch. */}
        <div key={activeTab} id="settings-tabpanel" role="tabpanel" aria-labelledby={`settings-tab-${activeTab}`} className="animate-tab-content space-y-6">
          {/* DETECTION SETTINGS */}
          {activeTab === 'detection' && (
            <div className="space-y-6">
              {/* Default Threshold card - professor-friendly */}
              <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400">
                    <Target size={18} />
                  </span>
                  <div className="flex-1">
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Default Similarity Threshold</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
                      Sets the minimum score for flagging a pair as suspicious. The Sensitivity preset (Review &amp; Workflow) sets this automatically; use the slider to fine-tune. Higher cutoff = fewer flags; lower = catches more but increases false positives.
                    </p>
                  </div>
                </div>
                <div className="mt-4 space-y-4">
                  <div className="flex items-center gap-6">
                    <input
                      type="range"
                      min="0.5"
                      max="1.0"
                      step="0.01"
                      value={threshold}
                      onChange={(event) => updateSetting('default_threshold', Number(event.target.value))}
                      aria-label="Default similarity threshold"
                      aria-valuetext={`${Math.round(threshold * 100)}% similarity`}
                      className="flex-1 accent-blue-600"
                    />
                    <div className="min-w-[4.5rem] text-right">
                      <span className="text-2xl font-semibold tabular-nums text-blue-600 dark:text-blue-400">{Math.round(threshold * 100)}%</span>
                      <div className="text-xs text-slate-500 dark:text-slate-400">cutoff</div>
                    </div>
                  </div>
                  <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400" aria-hidden="true">
                    <span>Flags more pairs</span>
                    <span>Flags fewer pairs</span>
                  </div>
                  <div role="group" aria-label="Sensitivity presets" className="grid gap-2 sm:grid-cols-3">
                    {SENSITIVITY_PRESETS.map((preset) => {
                      const selected = activePreset?.id === preset.id;
                      return (
                        <button
                          key={preset.id}
                          type="button"
                          onClick={() => updateSensitivity(preset.id)}
                          aria-pressed={selected}
                          className={`rounded-xl border px-3 py-2 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 ${selected
                            ? 'border-blue-600 bg-blue-50 dark:border-blue-500 dark:bg-blue-500/10'
                            : 'border-slate-200 bg-white hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:hover:bg-slate-900'
                            }`}
                        >
                          <span className="flex items-baseline justify-between gap-2">
                            <span className="text-sm font-semibold text-slate-900 dark:text-white">{preset.label}</span>
                            <span className="text-sm tabular-nums text-slate-500 dark:text-slate-400">{Math.round(SENSITIVITY_THRESHOLDS[preset.id] * 100)}%</span>
                          </span>
                          <span className="mt-0.5 block text-xs leading-5 text-slate-500 dark:text-slate-400">{preset.hint}</span>
                        </button>
                      );
                    })}
                  </div>
                  <p className="text-xs leading-5 text-slate-500 dark:text-slate-400">
                    {activePreset ? `Matches the ${activePreset.label} preset.` : 'Custom value between presets.'}{' '}
                    This is the default for new jobs and can be overridden per job.
                  </p>
                  {fieldErrors.default_threshold && (
                    <p role="alert" className="text-xs text-red-600 dark:text-red-400">{fieldErrors.default_threshold}</p>
                  )}
                </div>
              </section>

              {/* System Limits */}
              <Accordion
                title="System Limits"
                description="Control maximum file size, files per job, and processing batch size."
                isOpen={accordions.systemLimits}
                onToggle={() => setAccordions(prev => ({ ...prev, systemLimits: !prev.systemLimits }))}
              >
                <div className="grid gap-4 md:grid-cols-3">
                  <TextInput label="Max File Size (MB)" type="number" value={settings.max_file_size_mb} onChange={(value) => updateNumber('max_file_size_mb', value)} {...numberProps('max_file_size_mb')} />
                  <TextInput label="Max Files Per Job" type="number" value={settings.max_files_per_job} onChange={(value) => updateNumber('max_files_per_job', value)} {...numberProps('max_files_per_job')} />
                  <TextInput label="Processing Batch Size" type="number" value={settings.batch_size} onChange={(value) => updateNumber('batch_size', value)} {...numberProps('batch_size')} />
                </div>
                <div className="mt-3 rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-xs leading-5 text-slate-600 dark:text-slate-300">
                  <strong className="font-semibold">Tip:</strong> For large classes (&gt;100 students), increase batch size to 50-100 for faster processing. Reduce max file size if submissions contain large data files or binaries.
                </div>
              </Accordion>
            </div>
          )}

          {/* AI & EVIDENCE */}
          {activeTab === 'intelligence' && (
            <div className="space-y-6">
              {/* AI Providers Summary */}
              <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-400">
                    <Bot size={18} />
                  </span>
                  <div className="flex-1">
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">AI Provider Integration</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
                      Connect AI services for enhanced detection capabilities - AI-assisted rewrite analysis, code explanation generation, and evidence summarization.
                    </p>
                  </div>
                </div>
                {/* Provider picker: choose which vendor to configure */}
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {providers.map((spec: any) => {
                    const connected = providerStatus(spec).configured;
                    const isActive = activeProvider === spec.key;
                    return (
                      <button
                        key={spec.key}
                        type="button"
                        onClick={() => setSelectedProvider(spec.key)}
                        aria-pressed={isActive}
                        className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${isActive
                          ? 'border-blue-600 bg-blue-600 text-white shadow-sm'
                          : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-600 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-700 hover:text-slate-900 dark:hover:text-white'
                          }`}
                      >
                        <span className={`h-2 w-2 rounded-full ${connected ? 'bg-emerald-400' : isActive ? 'bg-white/50' : 'bg-slate-300 dark:bg-slate-600'}`} />
                        {spec.label}
                      </button>
                    );
                  })}
                </div>

                {activeSpec && (
                  <div className="mt-4 rounded-xl border border-slate-200 dark:border-slate-800 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <div className={`h-2.5 w-2.5 rounded-full ${activeStatus.configured ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'}`} />
                        <span className="text-sm font-semibold text-slate-900 dark:text-white">{activeSpec.label}</span>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${activeStatus.configured ? 'bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'}`}>
                          {activeStatus.label}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs font-medium text-blue-600 dark:text-blue-400">
                        {safeHref(activeSpec.key_url) && (
                          <a href={safeHref(activeSpec.key_url)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:underline">
                            Get API key <ExternalLink size={12} />
                          </a>
                        )}
                        {safeHref(activeSpec.docs_url) && (
                          <a href={safeHref(activeSpec.docs_url)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:underline">
                            Docs <ExternalLink size={12} />
                          </a>
                        )}
                      </div>
                    </div>
                    <div className="mt-3 space-y-3">
                      {activeSpec.requires_key ? (
                        <SecretInput
                          label="API Key"
                          value={(settings as any)?.llm_api_keys?.[activeProvider]}
                          configured={Boolean(configuredMap[activeProvider])}
                          placeholder={configuredMap[activeProvider] ? 'Leave blank to keep current key' : `Enter ${activeSpec.label} API key`}
                          onChange={(value) => setProviderKey(activeProvider, value)}
                        />
                      ) : (
                        <div className="rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-xs text-slate-500 dark:text-slate-400">
                          {activeSpec.label} does not require an API key (for example a locally hosted endpoint).
                        </div>
                      )}
                      <div className="grid gap-3 sm:grid-cols-2">
                        <TextInput
                          label="Base URL (optional)"
                          error={fieldErrors[`llm_base_urls:${activeProvider}`]}
                          autoComplete="off"
                          value={baseUrlsMap[activeProvider] ?? ''}
                          placeholder={activeSpec.base_url}
                          onChange={(value) => setProviderBaseUrl(activeProvider, value)}
                        />
                        <div>
                          <label className="mb-1.5 block text-xs font-semibold text-slate-600 dark:text-slate-300">Model</label>
                          <div className="flex gap-2">
                            <select
                              value={overridesMap[activeProvider] ?? ''}
                              onChange={(event) => setProviderModel(activeProvider, event.target.value)}
                              className="min-w-0 flex-1 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-white focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                            >
                              <option value="">Auto — always the newest recommended model</option>
                              {overridesMap[activeProvider] && !(modelOptions[activeProvider] || []).some((model: any) => model.id === overridesMap[activeProvider]) && (
                                <option value={overridesMap[activeProvider]}>{overridesMap[activeProvider]} (saved)</option>
                              )}
                              {(modelOptions[activeProvider] || []).map((model: any) => (
                                <option key={model.id} value={model.id}>
                                  {model.label}{model.tier && model.tier !== 'standard' ? ` — ${model.tier}` : ''}
                                </option>
                              ))}
                            </select>
                            <button
                              type="button"
                              disabled={modelsLoading[activeProvider]}
                              onClick={() => loadModels(activeProvider, true)}
                              title="Refresh the model list from the vendor"
                              className="rounded-lg border border-slate-200 dark:border-slate-800 p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-900 disabled:opacity-50"
                            >
                              <RefreshCw size={14} className={modelsLoading[activeProvider] ? 'animate-spin' : ''} />
                            </button>
                          </div>
                        </div>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {modelsLoading[activeProvider]
                          ? 'Loading models\u2026'
                          : `${(modelOptions[activeProvider] || []).length} models available`}
                        {modelSource[activeProvider] === 'live'
                          ? ' \u00b7 fetched live from the vendor'
                          : modelSource[activeProvider]
                            ? ' \u00b7 vendor\u2019s current recommendations (live list unavailable)'
                            : ''}
                      </p>
                      {modelMessage[activeProvider] && (
                        <div className="text-xs text-slate-500 dark:text-slate-400">{modelMessage[activeProvider]}</div>
                      )}
                      <button
                        type="button"
                        disabled={providerTest[activeProvider]?.testing}
                        onClick={() => testProvider(activeProvider)}
                        className="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-900 disabled:opacity-50"
                      >
                        {providerTest[activeProvider]?.testing ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                        {providerTest[activeProvider]?.testing ? 'Testing\u2026' : 'Test Connection'}
                      </button>
                      {providerTest[activeProvider]?.message && (
                        <div className={`text-xs ${providerTest[activeProvider].ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                          {providerTest[activeProvider].message}
                        </div>
                      )}
                    </div>
                    {activeSpec.note && (
                      <p className="mt-3 text-xs leading-5 text-slate-500 dark:text-slate-400">{activeSpec.note}</p>
                    )}
                  </div>
                )}
                {/* Default provider, and the one AI summaries fall back to when it fails. */}
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold text-slate-600 dark:text-slate-300">Default provider</label>
                    <select
                      value={String((settings as any)?.llm_provider || 'openai')}
                      onChange={(event) => updateSetting('llm_provider', event.target.value)}
                      className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-white focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                    >
                      {providers.length === 0 && <option value="openai">OpenAI</option>}
                      {providers.map((spec: any) => (
                        <option key={spec.key} value={spec.key}>{spec.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold text-slate-600 dark:text-slate-300">Fallback provider</label>
                    <select
                      value={String((settings as any)?.llm_fallback_provider || '')}
                      onChange={(event) => updateSetting('llm_fallback_provider', event.target.value)}
                      className="w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3 py-2 text-sm text-slate-900 dark:text-white focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                    >
                      <option value="">None</option>
                      {providers
                        .filter((spec: any) => spec.key !== String((settings as any)?.llm_provider || 'openai'))
                        .map((spec: any) => (
                          <option key={spec.key} value={spec.key}>{spec.label}</option>
                        ))}
                    </select>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Used for AI summaries when the default provider fails or has no key.</p>
                  </div>
                </div>
                <div className="mt-3 rounded-lg bg-blue-50 dark:bg-blue-500/10 p-3 text-xs leading-5 text-blue-700 dark:text-blue-300">
                  <strong className="font-semibold">Note:</strong> API keys are stored encrypted on the server and never shown again. Leave the field blank to keep an already-configured key.
                </div>
              </section>

              {/* Public Source Scanning */}
              <Accordion
                title="Public Source Scanning"
                description="Scan GitHub repositories and public websites to detect code copied from external sources."
                isOpen={accordions.publicSources}
                onToggle={() => setAccordions(prev => ({ ...prev, publicSources: !prev.publicSources }))}
              >
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${settings.source_scan_enabled ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'}`} aria-hidden="true" />
                    <span className="flex-1">
                      <span className="block text-sm font-semibold text-slate-900 dark:text-white">Enable public source scanning</span>
                      <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">
                        {settings.source_scan_enabled
                          ? sourceUrls.length > 0
                            ? `Active · tracking ${sourceUrls.length} source${sourceUrls.length !== 1 ? 's' : ''}`
                            : 'Active · no URLs yet — add at least one below'
                          : 'Compare submissions against public code repositories and URLs'}
                      </span>
                    </span>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={Boolean(settings.source_scan_enabled)}
                      aria-label="Enable public source scanning"
                      onClick={() => updateSetting('source_scan_enabled', !settings.source_scan_enabled)}
                      className={`relative h-6 w-11 shrink-0 rounded-full transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 ${settings.source_scan_enabled ? 'bg-blue-600' : 'bg-slate-300 dark:bg-slate-700'}`}
                    >
                      <span aria-hidden="true" className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${settings.source_scan_enabled ? 'left-[22px]' : 'left-0.5'}`} />
                    </button>
                  </div>

                  {settings.source_scan_enabled && (
                    <TextAreaInput
                      label="Source URLs (one per line)"
                      // Raw text is kept as typed and parsed separately. The box used to be rebuilt from the
                      // parsed list on every keystroke, which deleted a newline as soon as you typed it (so you
                      // could not start a new line) and split URLs that contain commas.
                      value={sourceUrlsText}
                      error={fieldErrors.source_scan_sites}
                      placeholder={'https://github.com/org/course-solutions\nhttps://raw.githubusercontent.com/org/repo/main/solution.py\nhttps://pastebin.com/raw/abc123'}
                      onChange={setSourceUrlsText}
                    />
                  )}
                </div>
              </Accordion>

              {/* Legacy Tools */}
              <Accordion
                title="Legacy Tools"
                description="MOSS integration for cross-referencing with the Measure of Software Similarity system."
                isOpen={accordions.legacyTools}
                onToggle={() => setAccordions(prev => ({ ...prev, legacyTools: !prev.legacyTools }))}
              >
                <div className="space-y-3">
                  <div className="rounded-lg bg-amber-50 dark:bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-300">
                    MOSS (Measure Of Software Similarity) is a legacy tool from Stanford. It provides an additional cross-reference for large classes.
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={`h-2.5 w-2.5 rounded-full ${settings.moss_user_id_configured ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'}`} />
                    <span className={`text-xs font-semibold ${settings.moss_user_id_configured ? 'text-emerald-700 dark:text-emerald-300' : 'text-slate-500 dark:text-slate-400'}`}>
                      {settings.moss_user_id_configured ? 'MOSS configured' : 'MOSS not configured'}
                    </span>
                  </div>
                  <SecretInput label="MOSS User ID" value={settings.moss_user_id} configured={Boolean(settings.moss_user_id_configured)} placeholder={settings.moss_user_id_configured ? 'Leave blank to keep current MOSS user ID' : 'Enter MOSS user ID'} onChange={(value) => updateSetting('moss_user_id', value)} />
                </div>
              </Accordion>

            </div>
          )}

          {/* REVIEW & WORKFLOW */}
          {activeTab === 'workflow' && (
            <div className="space-y-6">
              <SettingsGroup
                title="Quick setup"
                description="Start from the setup closest to your course, then adjust anything below. Nothing is saved until you click Save changes."
                icon={Target}
              >
                <div role="group" aria-label="Quick setup" className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {QUICK_SETUPS.map((setup) => {
                    const selected = activeQuickSetup?.id === setup.id;
                    return (
                      <button
                        key={setup.id}
                        type="button"
                        onClick={() => applyQuickSetup(setup)}
                        aria-pressed={selected}
                        className={`rounded-xl border px-3 py-2 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 ${selected
                          ? 'border-blue-600 bg-blue-50 dark:border-blue-500 dark:bg-blue-500/10'
                          : 'border-slate-200 bg-white hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:hover:bg-slate-900'
                          }`}
                      >
                        <span className="block text-sm font-semibold text-slate-900 dark:text-white">{setup.label}</span>
                        <span className="mt-0.5 block text-xs leading-5 text-slate-500 dark:text-slate-400">{setup.hint}</span>
                      </button>
                    );
                  })}
                </div>
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                  {activeQuickSetup ? `Current choices match ${activeQuickSetup.label}.` : 'Current choices are a custom mix.'}
                </p>
              </SettingsGroup>

              {/* The threshold and its presets live on the Detection tab only;
                  two editable copies used to disagree. */}
              <SettingsGroup
                title="Sensitivity & Threshold"
                description="Pairs at or above the flag threshold are marked for review."
                icon={Target}
              >
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-blue-50 dark:bg-blue-500/10 p-3 text-sm text-blue-700 dark:text-blue-300">
                  <span>
                    <span className="font-semibold">Flag threshold: {formatPct(settings.default_threshold ?? FALLBACK_THRESHOLD)}</span>
                    {' '}({activePreset ? `${activePreset.label} preset` : 'custom value'}). Each upload can still set its own.
                  </span>
                  <button
                    type="button"
                    onClick={() => setActiveTab('detection')}
                    className="shrink-0 rounded-lg border border-blue-200 bg-white px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50 dark:border-blue-500/30 dark:bg-slate-950 dark:text-blue-300"
                  >
                    Change on the Detection tab
                  </button>
                </div>
              </SettingsGroup>

              {/* Starter Code Handling */}
              <Accordion
                title="Starter Code Handling"
                description="Control how starter code, templates, and instructor-provided code are handled during comparisons."
                isOpen={accordions.starterCodeHandling}
                onToggle={() => setAccordions(prev => ({ ...prev, starterCodeHandling: !prev.starterCodeHandling }))}
              >
                <SegmentedOptions
                  label="Starter code handling"
                  options={catalog.starter_code_handling || []}
                  value={profile.starter_code_handling}
                  onChange={(value) => updateProfile('starter_code_handling', value)}
                />
                <div className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
                  {(catalog.starter_code_handling || []).find((o) => o.id === profile.starter_code_handling)?.description}
                </div>
              </Accordion>

              {/* Previous Term Matching */}
              <Accordion
                title="Previous Term Matching"
                description="Check submissions against work from previous semesters to identify cross-term reuse."
                isOpen={accordions.previousTermMatching}
                onToggle={() => setAccordions(prev => ({ ...prev, previousTermMatching: !prev.previousTermMatching }))}
              >
                <SegmentedOptions
                  label="Compare with earlier terms"
                  options={catalog.previous_term_matching || []}
                  value={profile.previous_term_matching || 'off'}
                  onChange={(value) => updateProfile('previous_term_matching', value)}
                />
                <div className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
                  {(catalog.previous_term_matching || []).find((o) => o.id === (profile.previous_term_matching || 'off'))?.description}
                  {' '}Only the closest few earlier submissions for each student are fully compared, so checks stay fast. Matches appear in the results labelled with their course and term.
                </div>
              </Accordion>

              {/* AI Rewrite Detection */}
              <Accordion
                title="AI Authorship Checks"
                description="Score each Plagiarism Checker submission for AI-generated code signals, alongside similarity."
                isOpen={accordions.aiRewriteDetection}
                onToggle={() => setAccordions(prev => ({ ...prev, aiRewriteDetection: !prev.aiRewriteDetection }))}
              >
                <SegmentedOptions
                  label="AI rewrite detection"
                  options={catalog.ai_rewrite_detection || []}
                  value={profile.ai_rewrite_detection === 'off' ? 'off' : 'balanced'}
                  onChange={(value) => updateProfile('ai_rewrite_detection', value)}
                />
                <div className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
                  {(catalog.ai_rewrite_detection || []).find((o) => o.id === (profile.ai_rewrite_detection === 'off' ? 'off' : 'balanced'))?.description}
                </div>
              </Accordion>

              {/* Review Queue Size */}
              <Accordion
                title="Pairs Shown on the Results Page"
                description="How many of the highest-scoring pairs the results page lists first. Reviewers can always show the rest."
                isOpen={accordions.reviewQueueSize}
                onToggle={() => setAccordions(prev => ({ ...prev, reviewQueueSize: !prev.reviewQueueSize }))}
              >
                <SegmentedOptions
                  label="Review queue size"
                  options={catalog.result_volume || []}
                  value={profile.result_volume}
                  onChange={(value) => updateProfile('result_volume', value)}
                />
              </Accordion>

              {/* Applied Profile Summary + Policy Details */}
              <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
                <div className="space-y-6">
                  <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-5 shadow-sm">
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">Active Profile Summary</div>
                    {applied.recommendation && (
                      <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">{applied.recommendation}</p>
                    )}
                    {applied.summary && (
                      <div className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm font-medium text-slate-900 dark:text-white">
                        {applied.summary}
                      </div>
                    )}

                    {/* What this means for you */}
                    <div className="mt-5 space-y-2 border-t border-slate-100 dark:border-slate-800 pt-4">
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 p-2.5">
                          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Flag threshold</span>
                          <div className="font-semibold text-slate-900 dark:text-white">{formatPct(settings.default_threshold ?? applied.threshold)} similar</div>
                        </div>
                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 p-2.5">
                          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Reviews shown</span>
                          <div className="font-semibold text-slate-900 dark:text-white">{applied.result_limit ?? 'All'}</div>
                        </div>
                      </div>
                    </div>
                  </section>

                  {applied.warnings?.length > 0 && (
                    <section className="rounded-xl border border-amber-200 dark:border-amber-500/20 bg-amber-50 dark:bg-amber-500/10 p-5 text-sm text-amber-800 dark:text-amber-300">
                      {applied.warnings.map((warning: string, i: number) => <div key={`${i}-${warning}`}>{warning}</div>)}
                    </section>
                  )}
                </div>

                <aside className="space-y-6">
                  {/* What these choices do on every check. This box used to list
                      features the pipeline did not have. */}
                  <section className="rounded-xl border border-blue-200 dark:border-blue-500/20 bg-blue-50 dark:bg-blue-500/10 p-5">
                    <div className="text-sm font-semibold text-blue-950 dark:text-blue-200">On every check</div>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-blue-800 dark:text-blue-300">
                      <li>{'\u2022'} {profile.starter_code_handling === 'include_starter_code' ? 'All code is compared, including starter code' : profile.starter_code_handling === 'ignore_starter_code' ? 'Uploaded starter code is removed before comparing' : 'Uploaded starter code and code most of the class shares are removed'}</li>
                      <li>{'\u2022'} {profile.ai_rewrite_detection === 'off' ? 'AI-authorship checks are off' : 'Each submission is also scored for AI-authorship signals'}</li>
                      {profile.previous_term_matching && profile.previous_term_matching !== 'off' && (
                        <li>{'\u2022'} {profile.previous_term_matching === 'same_course_only' ? 'Submissions are also checked against earlier offerings of the course' : 'Submissions are also checked against your earlier courses'}</li>
                      )}
                      <li>{'\u2022'} Pairs at or above {formatPct(settings.default_threshold ?? applied.threshold)} similarity are flagged (adjustable per upload)</li>
                      <li>{'\u2022'} Files too short to judge (a few lines) are never ranked above review</li>
                      <li>{'\u2022'} Public source scanning is {settings.source_scan_enabled ? 'on' : 'off'}</li>
                    </ul>
                  </section>

                  <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-5 shadow-sm">
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">Profile Quick Stats</div>
                    <div className="mt-3 space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 dark:text-slate-300">Sensitivity</span>
                        <span className="font-semibold text-slate-900 dark:text-white">{profile.sensitivity?.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()) || 'Balanced'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 dark:text-slate-300">AI Authorship Checks</span>
                        <span className="font-semibold text-slate-900 dark:text-white">{profile.ai_rewrite_detection === 'off' ? 'Off' : 'On'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 dark:text-slate-300">Starter Code</span>
                        <span className="font-semibold text-slate-900 dark:text-white text-right max-w-[180px]">{(catalog.starter_code_handling || []).find((o) => o.id === profile.starter_code_handling)?.label || profile.starter_code_handling?.replace(/_/g, ' ') || 'Student-written only'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 dark:text-slate-300">Previous Terms</span>
                        <span className="font-semibold text-slate-900 dark:text-white text-right max-w-[180px]">{(catalog.previous_term_matching || []).find((o) => o.id === (profile.previous_term_matching || 'off'))?.label || 'Off'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 dark:text-slate-300">Results Per Job</span>
                        <span className="font-semibold text-slate-900 dark:text-white">{profile.result_volume?.replace(/_/g, ' ').replace('top ', 'Top ') || 'Top 25'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 dark:text-slate-300">External Scan</span>
                        <span className={`font-semibold ${settings.source_scan_enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400 dark:text-slate-500'}`}>
                          {settings.source_scan_enabled ? 'Enabled' : 'Disabled'}
                        </span>
                      </div>
                    </div>
                  </section>
                </aside>
              </div>
            </div>
          )}

          {/* SYSTEM SETTINGS */}
          {activeTab === 'system' && (
            <div className="space-y-6">
              {/* Live Service Status */}
              <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400">
                    <Activity size={18} />
                  </span>
                  <div className="flex-1">
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Service Status</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
                      Live health of every service this app depends on{checkedSuffix(sysStatus?.checked_at)}.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void refreshSystemStatus()}
                    disabled={sysLoading}
                    className="flex shrink-0 items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-900 disabled:opacity-50"
                  >
                    {sysLoading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                    {sysLoading ? 'Checking…' : 'Refresh'}
                  </button>
                </div>
                {sysError && (
                  <div role="alert" className="mt-4 text-xs text-red-600 dark:text-red-400">{sysError}</div>
                )}
                {!sysStatus && !sysError && (
                  <div className="mt-4 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    <Loader2 size={16} className="animate-spin" /> Checking services…
                  </div>
                )}
                {sysStatus && (
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {(['database', 'embedding', 'gpu', 'storage', 'celery'] as const).map((key) => {
                      const svc = sysStatus.services[key];
                      if (!svc) return null;
                      return (
                        <div key={key} className={`rounded-lg border p-3 ${serviceTone(svc.status)}`}>
                          <div className="flex items-center justify-between gap-2">
                            <div className="text-xs font-semibold text-slate-600 dark:text-slate-300">{svc.label}</div>
                            {typeof svc.latency_ms === 'number' && svc.latency_ms > 0 && (
                              <div className="text-[11px] text-slate-400 dark:text-slate-500">{svc.latency_ms} ms</div>
                            )}
                          </div>
                          <div className="mt-1 flex items-center gap-2">
                            <span className={`inline-block h-2 w-2 rounded-full ${serviceDot(svc.status)}`} />
                            <span className="text-sm font-medium text-slate-900 dark:text-white">{serviceWord(svc.status)}</span>
                          </div>
                          {svc.detail ? <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{svc.detail}</div> : null}
                          {svc.base_url ? <div className="mt-0.5 truncate text-xs text-slate-400 dark:text-slate-500" title={svc.base_url}>{svc.base_url}</div> : null}
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>

              {/* Job Queue */}
              <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-400">
                    <Layers size={18} />
                  </span>
                  <div className="flex-1">
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Job Queue</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
                      Live queue depth, worker activity and active jobs{checkedSuffix(queueData?.checked_at)}.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void refreshQueue()}
                    disabled={queueLoading}
                    className="flex shrink-0 items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-900 disabled:opacity-50"
                  >
                    {queueLoading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                    {queueLoading ? 'Checking…' : 'Refresh'}
                  </button>
                  {killAllArmed ? (
                    <span className="flex shrink-0 items-center gap-2">
                      <button
                        type="button"
                        onClick={() => void killAllJobs()}
                        className="rounded-lg bg-red-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-red-700"
                      >
                        Confirm kill all ({queueData?.active_jobs.length ?? 0})
                      </button>
                      <button
                        type="button"
                        onClick={() => setKillAllArmed(false)}
                        className="rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-900"
                      >
                        Keep
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => { setKillAllArmed(true); setKillMessage(null); }}
                      disabled={(queueData?.active_jobs.length ?? 0) === 0}
                      title={(queueData?.active_jobs.length ?? 0) === 0 ? 'No active jobs to cancel' : undefined}
                      className="flex shrink-0 items-center gap-2 rounded-lg border border-red-200 dark:border-red-500/20 px-3 py-2 text-xs font-semibold text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50 dark:text-red-300 dark:hover:bg-red-500/10"
                    >
                      Kill all
                    </button>
                  )}
                </div>
                {queueError && (
                  <div role="alert" className="mt-4 text-xs text-red-600 dark:text-red-400">{queueError}</div>
                )}
                {!queueData && !queueError && (
                  <div className="mt-4 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    <Loader2 size={16} className="animate-spin" /> Checking queue…
                  </div>
                )}
                {queueData && (
                  <div className="mt-4 space-y-3">
                    <div className="flex flex-wrap gap-2">
                      {(['queued', 'processing', 'failed'] as const).map((status) => (
                        <span key={status} className="inline-flex items-center gap-2 rounded-full border border-slate-200 dark:border-slate-800 px-3 py-1 text-xs font-semibold text-slate-600 dark:text-slate-300">
                          <span className={`inline-block h-2 w-2 rounded-full ${status === 'queued' ? 'bg-amber-500' : status === 'processing' ? 'bg-blue-500' : 'bg-red-500'}`} />
                          {status}: {queueData.db_counts[status] ?? 0}
                        </span>
                      ))}
                      <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 dark:border-slate-800 px-3 py-1 text-xs font-semibold text-slate-600 dark:text-slate-300">
                        workers: {queueData.workers.length}
                      </span>
                    </div>
                    {queueData.celery_error && (
                      <div role="status" className="text-xs text-amber-700 dark:text-amber-300">
                        Worker detail unavailable: {queueData.celery_error}
                      </div>
                    )}
                    {queueData.workers.map((worker) => (
                      <div key={worker.name} className="text-xs text-slate-500 dark:text-slate-400">
                        <span className="font-semibold text-slate-700 dark:text-slate-200">{worker.name}</span>
                        {' '}· {worker.active.length} active{worker.reserved > 0 && ` · ${worker.reserved} reserved`}
                        {worker.active.slice(0, 3).map((task) => (
                          <span key={task.task_id || task.job_id || task.task} className="ml-2">
                            {task.job_id || task.task}{task.running_seconds !== undefined && task.running_seconds !== null ? ` (${queueAgeText(task.running_seconds)})` : ''}
                          </span>
                        ))}
                      </div>
                    ))}
                    {killMessage && (
                      <div role={killMessage.ok ? 'status' : 'alert'} className={`text-xs ${killMessage.ok ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-600 dark:text-red-400'}`}>
                        {killMessage.text}
                      </div>
                    )}
                    {queueData.active_jobs.length === 0 ? (
                      <div className="text-sm text-slate-500 dark:text-slate-400">No queued or running jobs.</div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="min-w-full text-left text-sm">
                          <thead>
                            <tr className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                              <th scope="col" className="px-3 py-2">Job</th>
                              <th scope="col" className="px-3 py-2">Status</th>
                              <th scope="col" className="px-3 py-2">Age</th>
                              <th scope="col" className="px-3 py-2"><span className="sr-only">Actions</span></th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                            {queueData.active_jobs.map((job) => (
                              <tr key={job.id}>
                                <td className="px-3 py-2">
                                  <div className="font-medium text-slate-900 dark:text-white">{job.name}</div>
                                  <div className="font-mono text-[11px] text-slate-400 dark:text-slate-500">{job.id.slice(0, 8)}</div>
                                </td>
                                <td className="px-3 py-2">
                                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${job.status === 'processing' ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'}`}>
                                    {job.status}
                                  </span>
                                </td>
                                <td className="px-3 py-2 text-slate-500 dark:text-slate-400">{queueAgeText(job.age_seconds)}</td>
                                <td className="px-3 py-2 text-right">
                                  {killArmed === job.id ? (
                                    <span className="inline-flex items-center gap-2">
                                      <button
                                        type="button"
                                        onClick={() => void killJob(job.id)}
                                        className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-red-700"
                                      >
                                        Confirm kill
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => setKillArmed(null)}
                                        className="rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-900"
                                      >
                                        Keep
                                      </button>
                                    </span>
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={() => { setKillArmed(job.id); setKillMessage(null); }}
                                      className="rounded-lg border border-red-200 dark:border-red-500/20 px-3 py-1.5 text-xs font-semibold text-red-700 transition hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-500/10"
                                    >
                                      Kill
                                    </button>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </section>

              {/* Notifications */}
              <Accordion
                title="Notifications"
                description="Hear when an analysis finishes, by email or at a webhook URL."
                isOpen={accordions.webhooks}
                onToggle={() => setAccordions(prev => ({ ...prev, webhooks: !prev.webhooks }))}
              >
                <div className="space-y-4">
                  <label className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={Boolean(settings.notify_email_on_finish)}
                      onChange={(event) => updateSetting('notify_email_on_finish', event.target.checked)}
                      className="mt-1 h-4 w-4 rounded border-slate-300 dark:border-slate-700 text-blue-600 dark:text-blue-400"
                    />
                    <span className="text-sm leading-6 text-slate-600 dark:text-slate-300">
                      <span className="font-medium text-slate-900 dark:text-white">Email the uploader when an analysis finishes</span>
                      <br />
                      Sends the number of submissions and flagged pairs with a link to the results, using the email delivery settings below. No student names or code are included.
                    </span>
                  </label>
                  <TextInput
                    label="Webhook URL (optional)"
                    value={webhookUrl}
                    onChange={setWebhookUrl}
                    placeholder="https://example.com/webhook"
                    autoComplete="off"
                    error={fieldErrors.webhook_url}
                  />
                  <p className="-mt-2 text-xs leading-5 text-slate-500 dark:text-slate-400">
                    Receives a signed JSON POST when an analysis finishes or fails, and an alert when one is stuck in the queue. Must be a public https address.
                  </p>
                </div>
              </Accordion>

              {/* Email Delivery */}
              <Accordion
                title="Email Delivery"
                description="Configure the mail backend used for password resets, review notifications, and test sends."
                isOpen={accordions.emailDelivery}
                onToggle={() => setAccordions(prev => ({ ...prev, emailDelivery: !prev.emailDelivery }))}
              >
                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <SelectInput
                      label="Backend"
                      value={(settings.email_backend as string) || 'console'}
                      options={[['console', 'Console (development only)'], ['smtp', 'SMTP server'], ['sendgrid', 'SendGrid API']]}
                      onChange={(value) => updateSetting('email_backend', value)}
                    />
                    <TextInput
                      label="From address"
                      value={(settings.email_from as string) || ''}
                      placeholder="noreply@your-university.edu"
                      autoComplete="off"
                      error={fieldErrors.email_from}
                      onChange={(value) => updateSetting('email_from', value)}
                    />
                  </div>

                  {settings.email_backend === 'smtp' && (
                    <div className="space-y-4 rounded-xl border border-slate-200 dark:border-slate-800 p-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <TextInput label="SMTP host" value={(settings.email_host as string) || ''} placeholder="smtp.your-university.edu" autoComplete="off" error={fieldErrors.email_host} onChange={(value) => updateSetting('email_host', value)} />
                        <TextInput label="SMTP port" type="number" value={(settings.email_port as number) ?? 587} onChange={(value) => updateNumber('email_port', value)} {...numberProps('email_port')} />
                        <TextInput label="SMTP username" value={(settings.email_user as string) || ''} placeholder="mailer@your-university.edu" autoComplete="off" onChange={(value) => updateSetting('email_user', value)} />
                        <SecretInput label="SMTP password" value={settings.email_password as string | null} configured={Boolean(settings.email_password_configured)} placeholder={settings.email_password_configured ? 'Leave blank to keep the current password' : 'Enter the SMTP password'} onChange={(value) => updateSetting('email_password', value)} />
                      </div>
                      <label className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={Boolean(settings.email_use_tls ?? true)}
                          onChange={(event) => updateSetting('email_use_tls', event.target.checked)}
                          className="mt-1 h-4 w-4 rounded border-slate-300 dark:border-slate-700 text-blue-600 dark:text-blue-400"
                        />
                        <span className="text-sm leading-6 text-slate-600 dark:text-slate-300">Use STARTTLS when connecting to the SMTP server.</span>
                      </label>
                      {!(settings.email_use_tls ?? true) && (
                        <p role="status" className="text-xs text-amber-700 dark:text-amber-300">
                          Without STARTTLS the SMTP username and password are sent unencrypted.
                        </p>
                      )}
                    </div>
                  )}

                  {settings.email_backend === 'sendgrid' && (
                    <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-4">
                      <SecretInput
                        label="SendGrid API key"
                        value={settings.sendgrid_api_key as string | null}
                        configured={Boolean(settings.sendgrid_api_key_configured)}
                        placeholder={settings.sendgrid_api_key_configured ? 'Leave blank to keep the current SendGrid key' : 'Enter your SendGrid API key'}
                        onChange={(value) => updateSetting('sendgrid_api_key', value)}
                      />
                    </div>
                  )}

                  {settings.email_backend === 'console' && (
                    <div className="rounded-lg bg-amber-50 dark:bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-300">
                      Console mode writes messages to the server log instead of sending them. Choose SMTP or SendGrid for real delivery.
                    </div>
                  )}

                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={sendTestEmail}
                      disabled={testingEmail || dirty}
                      className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-50"
                    >
                      {testingEmail ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                      {testingEmail ? 'Sending...' : 'Send test email'}
                    </button>
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {dirty
                        ? 'You have unsaved changes. Save them first: the test uses the configuration already stored on the server.'
                        : 'The test uses the configuration stored on the server.'}
                    </span>
                  </div>

                  {testEmailResult && (
                    <div role={testEmailResult.ok ? 'status' : 'alert'} className={`flex items-start gap-2 rounded-lg border p-3 text-sm ${testEmailResult.ok ? 'border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : 'border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-300'}`}>
                      {testEmailResult.ok ? <CheckCircle size={16} className="mt-0.5 shrink-0" /> : <XCircle size={16} className="mt-0.5 shrink-0" />}
                      <span>{testEmailResult.message}</span>
                    </div>
                  )}
                </div>
              </Accordion>

              {/* Configuration Validation */}
              <Accordion
                title="Configuration Check"
                description="Check your settings for common issues before running detection."
                isOpen={accordions.configValidation}
                onToggle={() => { setAccordions(prev => ({ ...prev, configValidation: !prev.configValidation })); if (!accordions.configValidation && !validationResult) validateConfig(); }}
              >
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={validateConfig}
                    disabled={validationLoading}
                    className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-50"
                  >
                    {validationLoading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                    {validationLoading ? 'Checking...' : 'Check My Settings'}
                  </button>
                </div>

                {validationResult && validationResult.issues && (
                  <div className="mt-4 space-y-2">
                    {validationResult.issues.length > 0 ? (
                      validationResult.issues.map((issue: string, i: number) => (
                        <div key={i} className="flex items-start gap-2 rounded-lg border border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300">
                          <XCircle size={16} className="mt-0.5 shrink-0" />
                          <span>{issue}</span>
                        </div>
                      ))
                    ) : (
                      <div className="flex items-start gap-2 rounded-lg border border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-300">
                        <CheckCircle size={16} className="mt-0.5 shrink-0" />
                        <span>Configuration looks healthy. No issues detected.</span>
                      </div>
                    )}
                  </div>
                )}

                {validationResult?.weight_governance?.needs_validation && (
                  <div className="mt-4 rounded-xl border border-amber-200 dark:border-amber-500/20 bg-amber-50 dark:bg-amber-500/10 p-4">
                    <div className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                      Weight change needs validation evidence
                    </div>
                    <p className="mt-1 text-xs leading-5 text-amber-800 dark:text-amber-300">
                      Default fusion weights were changed
                      {(validationResult.weight_governance.changed_engines || []).length > 0 && (
                        <> for <span className="font-semibold">{validationResult.weight_governance.changed_engines.join(', ')}</span></>
                      )}{' '}
                      without naming their validation proof. Shipping default weights requires a validation run on the
                      validation split (the locked test set stays untouched). Fill in the three fields to clear these warnings.
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void submitGovernanceAuto()}
                        disabled={govSaving}
                        className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:hover:bg-slate-900"
                      >
                        {govSaving ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                        Use latest benchmark run
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (govConfirmRevert) {
                            setGovConfirmRevert(false);
                            void submitGovernanceRevert();
                          } else {
                            setGovConfirmRevert(true);
                          }
                        }}
                        disabled={govSaving}
                        className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-semibold text-red-700 transition hover:bg-red-50 disabled:opacity-50 dark:border-red-500/20 dark:bg-slate-950 dark:text-red-300 dark:hover:bg-red-500/10"
                      >
                        <RefreshCw size={14} />
                        {govConfirmRevert ? 'Click again to confirm revert' : 'Revert to shipped defaults'}
                      </button>
                    </div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <TextInput
                        label="Validation run ID"
                        value={govForm.validation_run_id}
                        placeholder="e.g. val-2026-10-03-01"
                        autoComplete="off"
                        onChange={(value) => setGovForm((form) => ({ ...form, validation_run_id: value }))}
                      />
                      <TextInput
                        label="Benchmark dataset ID"
                        value={govForm.benchmark_dataset_id}
                        placeholder="e.g. pan2026-validation"
                        autoComplete="off"
                        onChange={(value) => setGovForm((form) => ({ ...form, benchmark_dataset_id: value }))}
                      />
                    </div>
                    <div className="mt-3">
                      <TextAreaInput
                        label="Metric snapshot"
                        value={govForm.metric_snapshot}
                        placeholder='e.g. F1 0.91, AUC-PR 0.93, FPR 0.03 (or paste JSON)'
                        onChange={(value) => setGovForm((form) => ({ ...form, metric_snapshot: value }))}
                      />
                    </div>
                    <div className="mt-2 text-xs text-amber-800 dark:text-amber-300">
                      Split: <span className="font-semibold">validation</span> (fixed — default weights must be tuned against the validation split, never the locked test set).
                    </div>
                    {auditEntries.length > 0 && (
                      <div className="mt-3 border-t border-amber-200/70 dark:border-amber-500/10 pt-3">
                        <div className="text-[11px] font-semibold uppercase tracking-wider text-amber-800 dark:text-amber-300">History</div>
                        <ul className="mt-1 space-y-1">
                          {auditEntries.slice(0, 5).map((entry) => (
                            <li key={entry.id} className="text-xs text-amber-800 dark:text-amber-300">
                              {AUDIT_ACTION_LABELS[entry.action] || entry.action}
                              {formatDateTime(entry.created_at) ? ` · ${formatDateTime(entry.created_at)}` : ''}
                              {typeof entry.allowed === 'boolean' ? (entry.allowed ? ' · allowed' : ' · flagged') : ''}
                              {typeof entry.evidence?.validation_run_id === 'string' && entry.evidence.validation_run_id ? ` · run ${entry.evidence.validation_run_id}` : ''}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {govMessage && (
                      <div role={govMessage.ok ? 'status' : 'alert'} className={`mt-3 text-xs ${govMessage.ok ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-600 dark:text-red-400'}`}>
                        {govMessage.text}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => void submitGovernanceEvidence()}
                      disabled={govSaving}
                      className="mt-3 inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:opacity-50"
                    >
                      {govSaving ? <Loader2 size={16} className="animate-spin" /> : <Shield size={16} />}
                      {govSaving ? 'Saving…' : 'Record validation evidence'}
                    </button>
                  </div>
                )}
              </Accordion>

              {/* Improve accuracy from past reviews */}
              <section className="rounded-2xl border border-amber-200 dark:border-amber-500/20 bg-amber-50 dark:bg-amber-500/10 p-5 shadow-sm">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 text-sm font-semibold text-amber-900 dark:text-amber-200">
                      <Activity size={16} />
                      Improve accuracy from past reviews
                    </div>
                    <p className="mt-1 text-sm leading-6 text-amber-700 dark:text-amber-300">
                      Use your past confirmed cases to fine-tune flagging for this course. Recommended only after you have reviewed at least 10 pairs.
                    </p>
                  </div>
                  {showCalibrateConfirm ? (
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={triggerCalibration}
                        disabled={calibrating}
                        className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:opacity-50"
                      >
                        {calibrating ? <Loader2 size={16} className="animate-spin" /> : <Activity size={16} />}
                        {calibrating ? 'Running...' : 'Confirm Calibration'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowCalibrateConfirm(false)}
                        className="rounded-lg border border-amber-300 bg-white dark:bg-slate-950 px-4 py-2 text-sm font-semibold text-amber-800 dark:text-amber-300 transition hover:bg-amber-100 dark:hover:bg-amber-500/15"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setShowCalibrateConfirm(true)}
                      disabled={dirty}
                      title={dirty ? 'Save or discard your changes first' : undefined}
                      className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Activity size={16} />
                      Run Calibration
                    </button>
                  )}
                </div>
                {calibResult && Object.keys(calibResult).length > 0 && (
                  <div className="mt-4 rounded-lg bg-white/70 dark:bg-slate-950/50 p-3">
                    <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-amber-900 dark:text-amber-200">
                      {Object.entries(calibResult).map(([metric, value]) => (
                        <span key={metric}>
                          {CALIB_METRIC_LABELS[metric] || metric}:{' '}
                          <strong className="font-semibold">{formatCalibMetric(metric, value)}</strong>
                        </span>
                      ))}
                    </div>
                    <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                      Read-only run — no settings were changed. If you agree with the best threshold, apply it from Detection Settings and save.
                    </p>
                  </div>
                )}
              </section>

              {/* Advanced: Embedding & Resource Settings */}
              <Accordion
                title="Advanced: embedding and resources"
                description="The model, hardware and server used to compare code submissions."
                isOpen={accordions.embeddingAdvanced}
                onToggle={() => setAccordions(prev => ({ ...prev, embeddingAdvanced: !prev.embeddingAdvanced }))}
              >
                <div className="space-y-4">
                  <div className="rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50 dark:bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-300">
                    These settings control how the system processes and compares code submissions. Changes apply when you save.
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    <SelectInput label="Embedding Runtime" value={settings.embedding_runtime} options={[['local_unixcoder', 'Local (UniXcoder)'], ['remote_openai_compatible', 'Remote Server']]} onChange={(value) => updateSetting('embedding_runtime', value)} />
                    <TextInput label="Embedding Model" value={settings.embedding_model || ''} placeholder="e.g. microsoft/unixcoder-base" onChange={(value) => updateSetting('embedding_model', value)} />
                    <SelectInput label="Hardware Acceleration" value={settings.embedding_device} options={[['auto', 'Auto'], ['cuda', 'CUDA / GPU'], ['cpu', 'CPU only']]} onChange={(value) => updateSetting('embedding_device', value)} />
                    <TextInput label="Embedding Batch Size" type="number" value={settings.embedding_batch_size} onChange={(value) => updateNumber('embedding_batch_size', value)} {...numberProps('embedding_batch_size')} />
                    <TextInput label="Embedding Server URL" value={settings.embedding_server_url || ''} placeholder="http://127.0.0.1:8001/v1" autoComplete="off" error={fieldErrors.embedding_server_url} onChange={(value) => updateSetting('embedding_server_url', value)} />
                    <TextInput label="Embedding Server Port" type="number" value={settings.embedding_server_port} onChange={(value) => updateNumber('embedding_server_port', value)} {...numberProps('embedding_server_port')} />
                  </div>
                </div>
              </Accordion>
            </div>
          )}
        </div>
      </div>

      {/* Floating save bar: the header's Save button scrolls out of view on the long System tab. */}
      {dirty && (
        <div className="pointer-events-none fixed inset-x-0 bottom-4 z-30 flex justify-center px-4">
          <div
            role="region"
            aria-label="Unsaved changes"
            className="pointer-events-auto flex w-full max-w-xl flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur dark:border-slate-700 dark:bg-slate-900/95"
          >
            <div className="text-sm text-slate-700 dark:text-slate-200">
              <span className="font-semibold">You have unsaved changes.</span>
              {errorCount > 0 && (
                <span className="ml-1 text-red-600 dark:text-red-400">
                  {errorCount} field{errorCount === 1 ? '' : 's'} need{errorCount === 1 ? 's' : ''} attention.
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={discardChanges}
                disabled={saving}
                className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:hover:bg-slate-900"
              >
                Discard
              </button>
              <button
                type="button"
                onClick={saveSettings}
                disabled={saving}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                {saving ? 'Saving...' : 'Save changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

function Accordion({ title, description, isOpen, onToggle, children }: { title: string; description?: string; isOpen: boolean; onToggle: () => void; children: React.ReactNode }) {
  // useId, not a slug of the title: two sections with similar titles used to share an id, and the
  // button pointed at a panel that does not exist while the section is collapsed.
  const panelId = useId();
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-sm">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-controls={isOpen ? panelId : undefined}
        className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-slate-50 dark:hover:bg-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500/40"
      >
        <div>
          <div className="text-lg font-semibold text-slate-900 dark:text-white">{title}</div>
          {description && (
            <div className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{description}</div>
          )}
        </div>
        <ChevronDown
          size={20}
          aria-hidden="true"
          className={`shrink-0 text-slate-400 dark:text-slate-500 transition-transform motion-reduce:transition-none ${isOpen ? 'rotate-180 text-blue-600 dark:text-blue-400' : ''}`}
        />
      </button>
      {isOpen && (
        <div id={panelId} className="border-t border-slate-200 dark:border-slate-800 px-5 pb-5 pt-4">
          {children}
        </div>
      )}
    </div>
  );
}

function SettingsGroup({ title, description, children, icon: Icon }: { title: string; description: string; children: React.ReactNode; icon?: React.ElementType }) {
  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-5 shadow-sm">
      <div className="flex items-start gap-3">
        {Icon && (
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            <Icon size={18} />
          </span>
        )}
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{description}</p>
        </div>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function SegmentedOptions({ label, options, value, onChange }: { label: string; options: { id: string; label: string }[]; value: string; onChange: (id: string) => void }) {
  // The options come from the server's catalog; without them this used to render nothing at all.
  if (options.length === 0) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">Options aren’t available right now. Reload the page.</p>;
  }

  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          onClick={() => onChange(option.id)}
          aria-pressed={value === option.id}
          className={`rounded-lg px-3 py-2 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 ${value === option.id ? 'bg-blue-600 text-white' : 'border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-900'
            }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

const FIELD_CLASS = 'mt-1 h-11 w-full rounded-lg border bg-white dark:bg-slate-900 px-3 text-sm text-slate-900 dark:text-white outline-none transition focus:ring-2';
const FIELD_OK = 'border-slate-200 dark:border-slate-800 focus:border-blue-500 dark:focus:border-blue-500 focus:ring-blue-500/20 dark:focus:ring-blue-500/20';
const FIELD_BAD = 'border-red-300 dark:border-red-500/50 focus:border-red-400 focus:ring-red-500/20 dark:focus:ring-red-500/20';

function FieldMessages({ id, error, hint }: { id?: string; error?: string; hint?: string }) {
  return (
    <>
      {error && <p id={id} role="alert" className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>}
      {!error && hint && <p id={id} className="mt-1 text-xs text-amber-700 dark:text-amber-300">{hint}</p>}
    </>
  );
}

function TextInput({ label, value, onChange, type = 'text', placeholder = '', error, hint, min, max, autoComplete }: { label: string; value: string | number; onChange: (value: string) => void; type?: string; placeholder?: string; error?: string; hint?: string; min?: number; max?: number; autoComplete?: string }) {
  const messageId = useId();
  const isNumber = type === 'number';
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{label}</span>
      <input
        type={type}
        value={value ?? ''}
        placeholder={placeholder}
        min={min}
        max={max}
        inputMode={isNumber ? 'numeric' : undefined}
        // Secret fields use "new-password" so a browser doesn't fill in the admin's own saved login.
        autoComplete={autoComplete}
        spellCheck={false}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? messageId : undefined}
        // A focused number box changes its value when the page is scrolled with the wheel or trackpad.
        onWheel={isNumber ? (event) => event.currentTarget.blur() : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={`${FIELD_CLASS} ${error ? FIELD_BAD : FIELD_OK}`}
      />
      <FieldMessages id={messageId} error={error} hint={hint} />
    </label>
  );
}

/**
 * A credential box. Blank keeps the saved value; "Remove" clears it on save (sent as null), so the
 * workspace falls back to the server's own key.
 */
function SecretInput({ label, value, configured, placeholder, onChange }: { label: string; value: string | null | undefined; configured: boolean; placeholder: string; onChange: (value: string | null) => void }) {
  if (value === null) {
    return (
      <div className="block">
        <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{label}</span>
        <div className="mt-1.5 flex items-center justify-between gap-3 rounded-lg border border-dashed border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-300">
          <span>Removed when you save. The server’s default is used instead, if it has one.</span>
          <button type="button" onClick={() => onChange('')} className="shrink-0 font-semibold underline">
            Undo
          </button>
        </div>
      </div>
    );
  }
  return (
    <div>
      <TextInput label={label} type="password" autoComplete="new-password" value={value || ''} placeholder={placeholder} onChange={onChange} />
      {configured && !value && (
        <button type="button" onClick={() => onChange(null)} className="mt-1 text-xs font-medium text-red-600 hover:underline dark:text-red-400">
          Remove saved {label.replace(/^SMTP /, '')}
        </button>
      )}
    </div>
  );
}

function TextAreaInput({ label, value, onChange, placeholder = '', error }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; error?: string }) {
  const messageId = useId();
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{label}</span>
      <textarea
        value={value ?? ''}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        rows={5}
        spellCheck={false}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? messageId : undefined}
        className={`mt-1 w-full rounded-lg border bg-white dark:bg-slate-900 px-3 py-3 text-sm text-slate-900 dark:text-white outline-none transition focus:ring-2 ${error ? FIELD_BAD : FIELD_OK}`}
      />
      <FieldMessages id={messageId} error={error} />
    </label>
  );
}

function SelectInput({ label, value, options, onChange }: { label: string; value: string; options: [string, string][]; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{label}</span>
      <select
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
        className={`${FIELD_CLASS} ${FIELD_OK}`}
      >
        {options.map(([optionId, optionLabel]) => <option key={optionId} value={optionId}>{optionLabel}</option>)}
      </select>
    </label>
  );
}

function Notice({ children, tone, icon: Icon }: { children: React.ReactNode; tone: 'red' | 'green'; icon: React.ElementType }) {
  const className = tone === 'red'
    ? 'border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-300'
    : 'border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300';
  return (
    <div role={tone === 'red' ? 'alert' : 'status'} className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${className}`}>
      <Icon size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}
