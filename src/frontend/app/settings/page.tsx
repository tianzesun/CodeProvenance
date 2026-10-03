// @ts-nocheck — TODO: add proper types (tracked in types/api.ts). Kept on purpose: this page reads
// ~60 loosely typed settings keys, so removing it needs the real `Settings` type from types/api.ts.

'use client';

import React from 'react';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '@/lib/apiClient';
import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { PageHeader } from '@/components/saas/SaaSPrimitives';
import {
  AlertTriangle,
  Bot,
  ChevronDown,
  Database,
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
};

interface ValidationResult {
  issues: string[];
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
  if (status === 401) {
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
  'gptzero_api_key',
  'grammarly_api_key',
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
  'audit_log_level',
  'audit_retention_days',
  'debug_mode',
  'email_backend',
  'email_host',
  'email_port',
  'email_user',
  'email_from',
  'email_use_tls',
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
  audit_retention_days: { min: 1, max: 36500, label: 'Audit retention' },
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
  audit_retention_days: 'system',
  embedding_server_url: 'system',
  embedding_server_port: 'system',
  embedding_batch_size: 'system',
};

const MAX_SOURCE_URLS = 100;
const FALLBACK_THRESHOLD = 0.75; // the "balanced" preset; was 0.82, which matched no preset

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
  return value === null || value === undefined || Number.isNaN(n) ? '—' : `${Math.round(n * 100)}%`;
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
      errors[key] = `${rule.label} must be between ${rule.min.toLocaleString('en-US')} and ${rule.max.toLocaleString('en-US')}.`;
    }
  }

  if (webhookUrl.trim() && !isHttpUrl(webhookUrl.trim())) {
    errors.webhook_url = 'Enter a full http(s) URL, for example https://example.com/webhook.';
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
 * "keep the stored one"); everything else is sent as shown. The page used to send every secret
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
    if (edited[key] && typeof value === 'string' && value.trim()) {
      payload[key] = value.trim();
    }
  }

  if (edited.llm_api_keys) {
    const keys: Record<string, string> = {};
    for (const [provider, value] of Object.entries((s.llm_api_keys || {}) as Record<string, unknown>)) {
      if (typeof value === 'string' && value.trim()) keys[provider] = value.trim();
    }
    if (Object.keys(keys).length > 0) payload.llm_api_keys = keys;
  }

  return payload;
}

const DEFAULT_PROFILE = {
  assignment_type: 'auto_detect',
  sensitivity: 'balanced',
  starter_code_handling: 'student_written_only',
  previous_term_matching: 'same_course_only',
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
      'Manage integration credentials, webhooks, email delivery, storage limits, and audit logging for this workspace.',
  },
];

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
  const [indicator, setIndicator] = useState<{ x: number; width: number } | null>(null);

  const syncIndicator = useCallback(() => {
    const list = tabListRef.current;
    const button = tabButtonRefs.current[activeTab];
    if (!list || !button) return;
    const listBox = list.getBoundingClientRect();
    const buttonBox = button.getBoundingClientRect();
    // Ignore zero-size measurements (hidden/collapsed container) so we never
    // park the pill at 0px and lose the active tab's background.
    if (buttonBox.width === 0 || listBox.width === 0) return;
    setIndicator({ x: buttonBox.left - listBox.left, width: buttonBox.width });
  }, [activeTab]);

  // Measure on mount and on every active-tab change. useLayoutEffect alone
  // missed the first paint because the tab bar mounts only after the settings
  // request resolves, and a missed measurement left the active tab invisible
  // until the user clicked another tab.
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
  }, [syncIndicator]);

  useEffect(() => {
    window.addEventListener('resize', syncIndicator);
    return () => window.removeEventListener('resize', syncIndicator);
  }, [syncIndicator]);

  const [accordions, setAccordions] = useState<Record<string, boolean>>({
    systemLimits: true,
    publicSources: true,
    legacyTools: false,
    webhooks: true,
    auditLogging: true,
    embeddingAdvanced: false,
    configValidation: false,
    starterCodeHandling: false,
    previousTermMatching: false,
    aiRewriteDetection: false,
    reviewQueueSize: false,
    aiDetectors: false,
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

  // Live provider connection test so the Connected badge reflects a verified
  // API call rather than merely the presence of a stored key.
  const [providerTest, setProviderTest] = useState<Record<string, { testing: boolean; message: string; ok: boolean }>>({});

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

  const setProviderKey = (provider: string, value: string) => {
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

  const validateConfig = async () => {
    setValidationLoading(true);
    try {
      const res = await apiClient.get('/api/settings/validation');
      setValidationResult(res.data);
    } catch (err: unknown) {
      setValidationResult({ issues: [describeError(err, 'Failed to validate the configuration.')] });
    } finally {
      setValidationLoading(false);
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
    try {
      const res = await apiClient.post('/api/settings/calibrate');
      showSuccess('Calibration completed: ' + (res.data?.message || 'OK'), 5000);
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
      setError(`Fix the ${errorKeys.length} highlighted field${errorKeys.length === 1 ? '' : 's'} before saving.`);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await apiClient.patch('/api/settings', buildPayload(settings, webhookUrl, sourceUrls, editedSecrets));
    } catch (err: unknown) {
      setError(describeError(err, 'Failed to save settings.'));
      setSaving(false);
      return;
    }

    // The save itself worked. A failed re-read must not be reported as a failed save.
    try {
      const fresh = await apiClient.get('/api/settings');
      applyLoaded(fresh.data);
      showSuccess('Settings saved. Recommended profile applied.');
    } catch {
      showSuccess('Settings saved, but the page couldn’t refresh. Reload to see the stored values.', 6000);
    }
    // Any earlier configuration check described the old settings.
    setValidationResult(null);
    setSaving(false);
  };

  const discardChanges = () => {
    if (serverSettingsRef.current) {
      applyLoaded(serverSettingsRef.current);
      setError(null);
    }
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
      <div className="theme-page-container space-y-6">
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
                {saving ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          }
          eyebrowStyle="badge"
        />

        {/* Notifications */}
        {error && <Notice tone="red" icon={AlertTriangle}>{error}</Notice>}
        {success && <Notice tone="green" icon={Shield}>{success}</Notice>}

        {/* Main Tab Navigation */}
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">Settings Categories</div>
        <div role="tablist" aria-label="Settings categories" className="relative flex flex-wrap gap-2 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-2 shadow-sm mb-6" ref={tabListRef}>
          {indicator && (
            <span
              aria-hidden="true"
              className="settings-tab-indicator absolute top-2 bottom-2 left-0 rounded-xl shadow-lg"
              style={{
                transform: `translateX(${indicator.x}px)`,
                width: indicator.width,
                backgroundColor: activeTabInfo?.accent ?? '#2563eb',
                boxShadow: `0 10px 24px -12px ${activeTabInfo?.accent ?? '#2563eb'}`,
              }}
            />
          )}
          {MAIN_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              ref={(node) => { tabButtonRefs.current[tab.id] = node; }}
              onClick={() => setActiveTab(tab.id)}
              role="tab"
              id={`settings-tab-${tab.id}`}
              aria-selected={activeTab === tab.id}
              aria-controls="settings-tabpanel"
              // The active tab always carries its own colour: before the pill
              // is measured it is the whole highlight, afterwards it simply
              // matches the pill sliding underneath it.
              className={`relative inline-flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-colors duration-200 ${activeTab === tab.id
                ? 'text-white shadow-lg'
                : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-900'
                }`}
              style={
                activeTab === tab.id
                  ? { backgroundColor: tab.accent, boxShadow: `0 10px 24px -12px ${tab.accent}` }
                  : undefined
              }
            >
              <tab.icon size={16} aria-hidden="true" />
              {tab.label}
              {errorsByTab[tab.id] > 0 && (
                <span
                  className="ml-0.5 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-bold text-white"
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
        <div key={activeTab} id="settings-tabpanel" role="tabpanel" aria-labelledby={`settings-tab-${activeTab}`} className="animate-tab-content space-y-8">
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
                    <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Default Similarity Threshold</h2>
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
                      value={settings.default_threshold ?? FALLBACK_THRESHOLD}
                      onChange={(event) => updateSetting('default_threshold', Number(event.target.value))}
                      aria-label="Default similarity threshold"
                      className="flex-1 accent-blue-600"
                    />
                    <div className="min-w-[5rem] text-right">
                      <span className="text-2xl font-bold text-blue-600 dark:text-blue-400">{((settings.default_threshold ?? FALLBACK_THRESHOLD) * 100).toFixed(0)}%</span>
                      <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">Cutoff</div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${(settings.default_threshold ?? FALLBACK_THRESHOLD) >= 0.8 ? 'bg-red-100 dark:bg-red-500/15 text-red-700 dark:text-red-300' : (settings.default_threshold ?? FALLBACK_THRESHOLD) >= 0.7 ? 'bg-amber-100 dark:bg-amber-500/15 text-amber-700 dark:text-amber-300' : 'bg-blue-100 dark:bg-blue-500/15 text-blue-700 dark:text-blue-300'}`}>
                      {(settings.default_threshold ?? FALLBACK_THRESHOLD) >= 0.8 ? 'Conservative' : (settings.default_threshold ?? FALLBACK_THRESHOLD) >= 0.7 ? 'Balanced' : 'Strict'}
                    </span>
                    <span className="text-xs text-slate-500 dark:text-slate-400 leading-6">This is the default for new jobs. Can be overridden per-job.</span>
                  </div>
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
                    <h2 className="text-lg font-semibold text-slate-950 dark:text-white">AI Provider Integration</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
                      Connect AI services for enhanced detection capabilities - AI-assisted rewrite analysis, code explanation generation, and evidence summarization.
                    </p>
                  </div>
                </div>
                {/* Provider picker: choose which vendor to configure */}
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {providers.map((spec: any) => {
                    const connected = Boolean(configuredMap[spec.key]);
                    const isActive = activeProvider === spec.key;
                    return (
                      <button
                        key={spec.key}
                        type="button"
                        onClick={() => setSelectedProvider(spec.key)}
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
                        <div className={`h-2.5 w-2.5 rounded-full ${configuredMap[activeSpec.key] ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'}`} />
                        <span className="text-sm font-semibold text-slate-900 dark:text-white">{activeSpec.label}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${configuredMap[activeSpec.key] ? 'bg-emerald-100 dark:bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'}`}>
                          {/* "Connected" claimed a working connection; this only reflects that a key is stored. */}
                          {configuredMap[activeSpec.key] ? 'Key stored' : 'Not configured'}
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
                        <TextInput
                          label="API Key"
                          type="password"
                          autoComplete="new-password"
                          value={(settings as any)?.llm_api_keys?.[activeProvider] ?? ''}
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
                {/* Default + fallback provider routing */}
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
                      {providers.map((spec: any) => (
                        <option key={spec.key} value={spec.key}>{spec.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
                {(settings as any)?.llm_fallback_provider && (settings as any)?.llm_fallback_provider === ((settings as any)?.llm_provider || 'openai') && (
                  <p role="status" className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                    The fallback provider is the same as the default, so it adds no redundancy.
                  </p>
                )}
                <div className="mt-3 rounded-lg bg-blue-50 dark:bg-blue-500/10 p-3 text-xs leading-5 text-blue-700 dark:text-blue-300">
                  <strong className="font-semibold">Note:</strong> API keys are stored encrypted and never exposed to the frontend. Leave the field blank to keep an already-configured key.
                </div>
              </section>

              {/* Public Source Scanning */}
              <Accordion
                title="Public Source Scanning"
                description="Scan GitHub repositories and public websites to detect code copied from external sources."
                isOpen={accordions.publicSources}
                onToggle={() => setAccordions(prev => ({ ...prev, publicSources: !prev.publicSources }))}
              >
                <div className="space-y-4">
                  <label className="flex items-start gap-3 rounded-xl border border-slate-200 dark:border-slate-800 p-4">
                    <input
                      type="checkbox"
                      checked={Boolean(settings.source_scan_enabled)}
                      onChange={(event) => updateSetting('source_scan_enabled', event.target.checked)}
                      className="mt-1 h-4 w-4 rounded border-slate-300 dark:border-slate-700 text-blue-600 dark:text-blue-400"
                    />
                    <span>
                      <span className="block text-sm font-semibold text-slate-950 dark:text-white">Enable public source scanning</span>
                      <span className="mt-1 block text-sm leading-6 text-slate-500 dark:text-slate-400">When enabled, each submission is compared against configured public code repositories and URLs.</span>
                    </span>
                  </label>

                  {settings.source_scan_enabled && (
                    <>
                      <div className="rounded-lg bg-blue-50 dark:bg-blue-500/10 p-3 text-sm text-blue-800 dark:text-blue-300">
                        <span className="font-semibold">Status:</span> Public scanning is active. Add URLs below for repositories to scan.
                        {sourceUrls.length > 0 && (
                          <span className="block mt-1">Currently tracking <strong>{sourceUrls.length}</strong> source{sourceUrls.length !== 1 ? 's' : ''}.</span>
                        )}
                      </div>
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
                    </>
                  )}

                  {!settings.source_scan_enabled && (
                    <div className="rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm text-slate-500 dark:text-slate-400">
                      Enable the toggle above to configure public source URLs.
                    </div>
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
                  <TextInput label="MOSS User ID" type="password" autoComplete="off" value={settings.moss_user_id} placeholder={settings.moss_user_id_configured ? 'Leave blank to keep current MOSS user ID' : 'Enter MOSS user ID'} onChange={(value) => updateSetting('moss_user_id', value)} />
                </div>
              </Accordion>

              {/* AI Detectors (GPTZero / Grammarly) */}
              <Accordion
                title="AI Detectors"
                description="Connect third-party AI-writing detectors used to score essay and report submissions."
                isOpen={accordions.aiDetectors}
                onToggle={() => setAccordions(prev => ({ ...prev, aiDetectors: !prev.aiDetectors }))}
              >
                <div className="space-y-4">
                  {([
                    ['gptzero_api_key', 'GPTZero', 'GPTZero estimates AI-generation probability and returns per-sentence scores.'],
                    ['grammarly_api_key', 'Grammarly', 'Grammarly adds tone, grammar, and writing-assistance signals for textual submissions.'],
                  ] as [string, string, string][]).map(([key, name, help]) => (
                    <div key={key} className="rounded-xl border border-slate-200 dark:border-slate-800 p-4">
                      <div className="flex items-center gap-3">
                        <div className={`h-2.5 w-2.5 rounded-full ${settings[`${key}_configured`] ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'}`} />
                        <span className={`text-xs font-semibold ${settings[`${key}_configured`] ? 'text-emerald-700 dark:text-emerald-300' : 'text-slate-500 dark:text-slate-400'}`}>
                          {settings[`${key}_configured`] ? `${name} configured` : `${name} not configured`}
                        </span>
                      </div>
                      <div className="mt-3">
                        <TextInput
                          label={`${name} API Key`}
                          type="password"
                          autoComplete="new-password"
                          value={(settings[key] as string) || ''}
                          placeholder={settings[`${key}_configured`] ? `Leave blank to keep the current ${name} key` : `Enter your ${name} API key`}
                          onChange={(value) => updateSetting(key, value)}
                        />
                      </div>
                      <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-slate-400">{help}</p>
                    </div>
                  ))}
                  <div className="rounded-lg bg-blue-50 dark:bg-blue-500/10 p-3 text-xs leading-5 text-blue-700 dark:text-blue-300">
                    <strong className="font-semibold">Note:</strong> Keys are stored server-side and never returned to the browser. Leave a field blank to keep an already-configured key.
                  </div>
                </div>
              </Accordion>
            </div>
          )}

          {/* REVIEW & WORKFLOW */}
          {activeTab === 'workflow' && (
            <div className="space-y-6">
              {/* Sensitivity & Detection Profile */}
              <SettingsGroup
                title="Sensitivity & Threshold"
                description="How aggressively should the system flag submissions? Conservative has fewer false positives; Strict catches more cases."
                icon={Target}
              >
                <SegmentedOptions
                  options={catalog.sensitivities || catalog.review_modes || []}
                  value={profile.sensitivity}
                  onChange={updateSensitivity}
                />
                <div className="mt-4 rounded-lg bg-blue-50 dark:bg-blue-500/10 p-3 text-sm text-blue-700 dark:text-blue-300">
                  <span className="font-semibold">Preset cutoff: </span>
                  {profile.sensitivity === 'conservative' && '\u226584% similarity - best for formal investigations'}
                  {profile.sensitivity === 'balanced' && '\u226575% similarity - recommended default'}
                  {profile.sensitivity === 'strict' && '\u226564% similarity - shows more cases for early triage'}
                  <span className="block mt-1">This sets the default cutoff for new jobs. Fine-tune the exact value with the threshold slider.</span>
                  {SENSITIVITY_THRESHOLDS[profile.sensitivity] !== undefined
                    && Math.abs(Number(settings.default_threshold ?? FALLBACK_THRESHOLD) - SENSITIVITY_THRESHOLDS[profile.sensitivity]) > 0.005 && (
                    <span className="block mt-1 font-semibold">
                      The current cutoff is {formatPct(settings.default_threshold)} (a custom value, not the preset).
                    </span>
                  )}
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
                  options={catalog.starter_code_handling || []}
                  value={profile.starter_code_handling}
                  onChange={(value) => updateProfile('starter_code_handling', value)}
                />
                <div className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
                  {profile.starter_code_handling === 'ignore_starter_code' && 'Starter code is completely excluded from all comparisons. Best for large shared codebases.'}
                  {profile.starter_code_handling === 'student_written_only' && 'Only the student-written portions are compared. Shared starter code segments are discounted. Recommended default.'}
                  {profile.starter_code_handling === 'include_starter_code' && 'Full submission including starter code is compared. May increase false positives from template code.'}
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
                  options={catalog.previous_term_matching || []}
                  value={profile.previous_term_matching}
                  onChange={(value) => updateProfile('previous_term_matching', value)}
                />
                <div className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
                  {profile.previous_term_matching === 'off' && 'No cross-term comparison will be performed. Past submissions are ignored.'}
                  {profile.previous_term_matching === 'same_course_only' && 'Compares against submissions from the same course in previous terms only. Recommended default.'}
                  {profile.previous_term_matching === 'all_historical_courses' && 'Compares against all historical submissions across all courses. Most comprehensive but may increase review volume.'}
                </div>
              </Accordion>

              {/* AI Rewrite Detection */}
              <Accordion
                title="AI Rewrite Detection"
                description="Detect AI-assisted code rewrites, paraphrasing, and structural reorganization."
                isOpen={accordions.aiRewriteDetection}
                onToggle={() => setAccordions(prev => ({ ...prev, aiRewriteDetection: !prev.aiRewriteDetection }))}
              >
                <SegmentedOptions
                  options={catalog.ai_rewrite_detection || []}
                  value={profile.ai_rewrite_detection}
                  onChange={(value) => updateProfile('ai_rewrite_detection', value)}
                />
                <div className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
                  {profile.ai_rewrite_detection === 'off' && 'AI-assisted rewrite detection is disabled. Only direct similarity is checked.'}
                  {profile.ai_rewrite_detection === 'balanced' && 'Detects obvious AI rewrites while keeping false positives low. Recommended default.'}
                  {profile.ai_rewrite_detection === 'aggressive' && 'Maximum detection sensitivity for AI rewrites. Uses AST/CFG analysis to catch paraphrased logic. May increase false positives.'}
                </div>
              </Accordion>

              {/* Review Queue Size */}
              <Accordion
                title="Review Queue Size"
                description="How many results should appear in your review list. Top 25 works well for most assignments."
                isOpen={accordions.reviewQueueSize}
                onToggle={() => setAccordions(prev => ({ ...prev, reviewQueueSize: !prev.reviewQueueSize }))}
              >
                <SegmentedOptions
                  options={catalog.result_volume || []}
                  value={profile.result_volume}
                  onChange={(value) => updateProfile('result_volume', value)}
                />
              </Accordion>

              {/* Applied Profile Summary + Policy Details */}
              <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
                <div className="space-y-6">
                  <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-5 shadow-sm">
                    <div className="text-sm font-semibold text-slate-950 dark:text-white">Active Profile Summary</div>
                    <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">{applied.recommendation}</p>
                    <div className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm font-medium text-slate-950 dark:text-white">
                      {applied.summary}
                    </div>

                    {/* What this means for you */}
                    <div className="mt-5 space-y-2 border-t border-slate-100 dark:border-slate-800 pt-4">
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div className="rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 p-2.5">
                          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Flag threshold</span>
                          <div className="font-semibold text-slate-900 dark:text-white">{formatPct(applied.threshold)} similar</div>
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
                      {applied.warnings.map((warning: string) => <div key={warning}>{warning}</div>)}
                    </section>
                  )}
                </div>

                <aside className="space-y-6">
                  <section className="rounded-xl border border-blue-200 dark:border-blue-500/20 bg-blue-50 dark:bg-blue-500/10 p-5">
                    <div className="text-sm font-semibold text-blue-950">System handles automatically</div>
                    <div className="mt-3 space-y-2 text-sm leading-6 text-blue-800 dark:text-blue-300">
                      <div>{'\u2022'} Starter code is excluded from comparisons</div>
                      <div>{'\u2022'} Previous-term submissions are matched when available</div>
                      <div>{'\u2022'} Runtime behavior and identical wrong answers are compared</div>
                      <div>{'\u2022'} Thresholds are automatically adjusted</div>
                    </div>
                  </section>

                  <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-5 shadow-sm">
                    <div className="text-sm font-semibold text-slate-950 dark:text-white">Profile Quick Stats</div>
                    <div className="mt-3 space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 dark:text-slate-300">Sensitivity</span>
                        <span className="font-semibold text-slate-900 dark:text-white">{profile.sensitivity?.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()) || 'Balanced'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 dark:text-slate-300">AI Rewrite Detection</span>
                        <span className="font-semibold text-slate-900 dark:text-white">{profile.ai_rewrite_detection?.replace(/\b\w/g, (l: string) => l.toUpperCase()) || 'Balanced'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 dark:text-slate-300">Starter Code</span>
                        <span className="font-semibold text-slate-900 dark:text-white text-right max-w-[180px]">{profile.starter_code_handling?.replace(/_/g, ' ') || 'Student-written only'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600 dark:text-slate-300">Previous Terms</span>
                        <span className="font-semibold text-slate-900 dark:text-white text-right max-w-[180px]">{profile.previous_term_matching?.replace(/_/g, ' ') || 'Same course only'}</span>
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
              {/* Database & System Health Card */}
              <section className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400">
                    <Database size={18} />
                  </span>
                  <div className="flex-1">
                    <h2 className="text-lg font-semibold text-slate-950 dark:text-white">Database & System Health</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">Current connection status and system information.</p>
                  </div>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {/* This tile used to say "Connected · Neon PostgreSQL" unconditionally, whatever the real state.
                      It now shows what the settings response reports, or says nothing was reported. */}
                  {(() => {
                    const reported = String((settings as any).database_status ?? '').toLowerCase();
                    const known = reported !== '';
                    const healthy = ['ok', 'connected', 'healthy', 'up'].includes(reported);
                    const tone = !known
                      ? 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900'
                      : healthy
                        ? 'border-emerald-200 dark:border-emerald-500/20 bg-emerald-50 dark:bg-emerald-500/10'
                        : 'border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10';
                    return (
                      <div className={`rounded-lg border p-3 ${tone}`}>
                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300">Database</div>
                        <div className="mt-1 flex items-center gap-2">
                          <span className={`inline-block h-2 w-2 rounded-full ${!known ? 'bg-slate-300 dark:bg-slate-600' : healthy ? 'bg-emerald-500' : 'bg-red-500'}`} />
                          <span className="text-sm font-medium text-slate-900 dark:text-white">
                            {!known ? 'Status not reported' : healthy ? 'Connected' : reported}
                          </span>
                        </div>
                        {(settings as any).database_provider && (
                          <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{String((settings as any).database_provider)}</div>
                        )}
                      </div>
                    );
                  })()}
                  <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300">Default Threshold</div>
                    <div className="mt-1 text-sm font-medium text-slate-900 dark:text-white">{(Number(settings.default_threshold ?? FALLBACK_THRESHOLD) * 100).toFixed(0)}%</div>
                    <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">Similarity cutoff</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300">Debug Mode</div>
                    <div className="mt-1 text-sm font-medium text-slate-900 dark:text-white">
                      {settings.debug_mode ? (
                        <span className="text-amber-600 dark:text-amber-400">Enabled</span>
                      ) : (
                        <span className="text-slate-600 dark:text-slate-300">Disabled</span>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">Verbose logging</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300">Embedding Runtime</div>
                    <div className="mt-1 text-sm font-medium text-slate-900 dark:text-white capitalize">{settings.embedding_runtime?.replace(/_/g, ' ') || '—'}</div>
                    <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{settings.embedding_model || '—'}</div>
                  </div>
                </div>
              </section>

              {/* Webhooks */}
              <Accordion
                title="Webhooks"
                description="Configure webhooks for real-time notifications when jobs complete or flag high-risk submissions."
                isOpen={accordions.webhooks}
                onToggle={() => setAccordions(prev => ({ ...prev, webhooks: !prev.webhooks }))}
              >
                <TextInput label="Webhook URL" value={webhookUrl} onChange={setWebhookUrl} placeholder="https://example.com/webhook" autoComplete="off" error={fieldErrors.webhook_url} hint={webhookUrl.trim().startsWith('http://') ? 'This URL is not encrypted (http). Use https for anything outside a trusted network.' : undefined} />
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
                        <TextInput label="SMTP password" type="password" autoComplete="new-password" value={(settings.email_password as string) || ''} placeholder={settings.email_password_configured ? 'Leave blank to keep the current password' : 'Enter the SMTP password'} onChange={(value) => updateSetting('email_password', value)} />
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
                      <TextInput
                        label="SendGrid API key"
                        type="password"
                        autoComplete="new-password"
                        value={(settings.sendgrid_api_key as string) || ''}
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
                      className="inline-flex items-center gap-2 rounded-lg bg-slate-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
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

              {/* Audit & Logging */}
              <Accordion
                title="Audit & Logging"
                description="Configure audit log level and retention policy for compliance and debugging."
                isOpen={accordions.auditLogging}
                onToggle={() => setAccordions(prev => ({ ...prev, auditLogging: !prev.auditLogging }))}
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <SelectInput label="Audit Log Level" value={settings.audit_log_level || 'INFO'} options={[['DEBUG', 'Debug'], ['INFO', 'Info'], ['WARNING', 'Warning'], ['ERROR', 'Error']]} onChange={(value) => updateSetting('audit_log_level', value)} />
                  <TextInput label="Audit Retention (days)" type="number" value={settings.audit_retention_days ?? 365} onChange={(value) => updateNumber('audit_retention_days', value)} {...numberProps('audit_retention_days')} hint={typeof settings.audit_retention_days === 'number' && settings.audit_retention_days < 90 ? 'Below the 90-day compliance minimum recommended here.' : undefined} />
                </div>
                <div className="mt-4 rounded-lg bg-amber-50 dark:bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-300">
                  Audit logs older than the retention period may be automatically pruned. Keep a minimum of 90 days for compliance.
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
                    className="inline-flex items-center gap-2 rounded-lg bg-slate-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
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
              </Accordion>

              {/* Improve accuracy from past reviews */}
              <section className="rounded-xl border border-amber-200 dark:border-amber-500/20 bg-amber-50 dark:bg-amber-500/10 p-5 shadow-sm">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
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
              </section>

              {/* Advanced: Embedding & Resource Settings */}
              <button
                type="button"
                onClick={() => setAccordions(prev => ({ ...prev, embeddingAdvanced: !prev.embeddingAdvanced }))}
                aria-expanded={accordions.embeddingAdvanced}
                className="flex w-full items-center justify-between rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 px-4 py-2.5 text-left text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <span className="flex items-center gap-2">
                  <Zap size={16} />
                  Advanced: Embedding & Resource Settings
                </span>
                <span>{accordions.embeddingAdvanced ? 'Hide' : 'Show'}</span>
              </button>

              {accordions.embeddingAdvanced && (
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
              )}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

function Accordion({ title, description, isOpen, onToggle, children }: { title: string; description?: string; isOpen: boolean; onToggle: () => void; children: React.ReactNode }) {
  const panelId = `accordion-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-controls={panelId}
        className="flex w-full items-center justify-between px-5 py-4 text-left transition-colors hover:bg-slate-50 dark:hover:bg-slate-900 focus-visible:ring-2 focus-visible:ring-blue-200 rounded-t-2xl"
      >
        <div>
          <div className="text-lg font-semibold text-slate-950 dark:text-white">{title}</div>
          {description && (
            <div className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{description}</div>
          )}
        </div>
        <ChevronDown
          size={20}
          aria-hidden="true"
          className={`text-slate-400 dark:text-slate-500 transition-transform ${isOpen ? 'rotate-180 text-blue-600 dark:text-blue-400' : ''}`}
        />
      </button>
      {isOpen && (
        <div id={panelId} className="border-t border-slate-200 dark:border-slate-800 px-5 pb-5 pt-4 transition-all duration-200">
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
          <h2 className="text-lg font-semibold text-slate-950 dark:text-white">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{description}</p>
        </div>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function SegmentedOptions({ options, value, onChange }: { options: { id: string; label: string }[]; value: string; onChange: (id: string) => void }) {
  // The options come from the server's catalog; without them this used to render nothing at all.
  if (options.length === 0) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">Options aren’t available right now. Reload the page.</p>;
  }

  return (
    <div role="group" className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          onClick={() => onChange(option.id)}
          aria-pressed={value === option.id}
          className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${value === option.id ? 'bg-blue-600 text-white' : 'border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-900'
            }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

const FIELD_CLASS = 'mt-1 h-11 w-full rounded-lg border bg-white dark:bg-slate-900 px-3 text-sm text-slate-900 dark:text-white outline-none transition focus:ring-4';
const FIELD_OK = 'border-slate-200 dark:border-slate-800 focus:border-blue-300 dark:focus:border-blue-500 focus:ring-blue-50 dark:focus:ring-blue-500/20';
const FIELD_BAD = 'border-red-300 dark:border-red-500/50 focus:border-red-400 focus:ring-red-100 dark:focus:ring-red-500/20';

function FieldMessages({ error, hint }: { error?: string; hint?: string }) {
  return (
    <>
      {error && <p role="alert" className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>}
      {!error && hint && <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">{hint}</p>}
    </>
  );
}

function TextInput({ label, value, onChange, type = 'text', placeholder = '', error, hint, min, max, autoComplete }: { label: string; value: string | number; onChange: (value: string) => void; type?: string; placeholder?: string; error?: string; hint?: string; min?: number; max?: number; autoComplete?: string }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{label}</span>
      <input
        type={type}
        value={value ?? ''}
        placeholder={placeholder}
        min={min}
        max={max}
        inputMode={type === 'number' ? 'numeric' : undefined}
        // Secret fields use "new-password" so a browser doesn't fill in the admin's own saved login.
        autoComplete={autoComplete}
        spellCheck={false}
        aria-invalid={error ? true : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={`${FIELD_CLASS} ${error ? FIELD_BAD : FIELD_OK}`}
      />
      <FieldMessages error={error} hint={hint} />
    </label>
  );
}

function TextAreaInput({ label, value, onChange, placeholder = '', error }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; error?: string }) {
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
        className={`mt-1 w-full rounded-lg border bg-white dark:bg-slate-900 px-3 py-3 text-sm text-slate-900 dark:text-white outline-none transition focus:ring-4 ${error ? FIELD_BAD : FIELD_OK}`}
      />
      <FieldMessages error={error} />
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
        {options.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
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
