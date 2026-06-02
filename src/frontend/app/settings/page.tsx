'use client';

import { useEffect, useMemo, useState } from 'react';
import { apiClient } from '@/lib/apiClient';
import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { ButtonLink, PageHeader } from '@/components/saas/SaaSPrimitives';
import {
  AlertTriangle,
  Bot,
  ChevronDown,
  Cpu,
  Database,
  ExternalLink,
  FileCog,
  FolderTree,
  GitMerge,
  Landmark,
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
  Eye,
  XCircle,
  CheckCircle,
  FileText,
  BarChart3,
  Users,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

const DEFAULT_PROFILE = {
  assignment_type: 'auto_detect',
  sensitivity: 'balanced',
  starter_code_handling: 'student_written_only',
  previous_term_matching: 'same_course_only',
  ai_rewrite_detection: 'balanced',
  result_volume: 'top_25',
  external_source_scan: true,
};

// 4 main categories - each shows all sections on one page
const MAIN_TABS = [
  { id: 'detection', label: 'Detection Settings', icon: FolderTree },
  { id: 'intelligence', label: 'AI & Evidence', icon: Brain },
  { id: 'workflow', label: 'Review & Workflow', icon: Workflow },
  { id: 'system', label: 'System Settings', icon: Server },
];

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [settings, setSettings] = useState<any | null>(null);
  const [activeTab, setActiveTab] = useState<string>('detection');
  const [webhookUrl, setWebhookUrl] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showEngineWeights, setShowEngineWeights] = useState(false);
  const [showPerformanceAdvanced, setShowPerformanceAdvanced] = useState(false);
  const [validationResult, setValidationResult] = useState<any | null>(null);
  const [validationLoading, setValidationLoading] = useState<boolean>(false);
  const [calibrating, setCalibrating] = useState<boolean>(false);
  const [showCalibrateConfirm, setShowCalibrateConfirm] = useState<boolean>(false);
  const [engineConfig, setEngineConfig] = useState<any | null>(null);
  const [configLoading, setConfigLoading] = useState<boolean>(false);

  const [accordions, setAccordions] = useState<Record<string, boolean>>({
    systemLimits: true,
    publicSources: true,
    legacyTools: false,
    webhooks: true,
    auditLogging: true,
    detectionThreshold: false,
    embeddingAdvanced: false,
    configValidation: false,
    starterCodeHandling: false,
    previousTermMatching: false,
    aiRewriteDetection: false,
    reviewQueueSize: false,
  });

  useEffect(() => {
    if (authLoading || !user) return;
    apiClient.get('/api/settings')
      .then((res) => {
        setSettings(res.data);
        setWebhookUrl(res.data.webhook_url || '');
      })
      .catch(() => setError('Failed to load settings'));
  }, [authLoading, user]);

  const profile = settings?.professor_profile || DEFAULT_PROFILE;
  const catalog = settings?.professor_profile_catalog || {};
  const applied = settings?.applied_professor_profile || {};
  const engineWeightTotal = useMemo(
    () => {
      const weights = settings?.engine_weights || {};
      return Object.values(weights).reduce((sum: number, weight: unknown) => sum + Number(weight || 0), 0);
    },
    [settings?.engine_weights],
  );

  const updateSetting = (key: string, value: unknown) => {
    setSettings((current: any) => ({ ...current, [key]: value }));
  };

  const updateProfile = (key: string, value: unknown) => {
    setSettings((current: any) => ({
      ...current,
      professor_profile: {
        ...(current?.professor_profile || DEFAULT_PROFILE),
        [key]: value,
      },
    }));
  };

  const validateConfig = async () => {
    setValidationLoading(true);
    try {
      const res = await apiClient.get('/api/settings/validation');
      setValidationResult(res.data);
    } catch (err: any) {
      setValidationResult({ issues: ['Failed to validate configuration: ' + (err?.response?.data?.detail || err.message)] });
    } finally {
      setValidationLoading(false);
    }
  };

  const loadEngineConfig = async () => {
    setConfigLoading(true);
    try {
      const res = await apiClient.get('/api/settings/engine-config');
      setEngineConfig(res.data);
    } catch {
      setEngineConfig(null);
    } finally {
      setConfigLoading(false);
    }
  };

  const triggerCalibration = async () => {
    setCalibrating(true);
    try {
      const res = await apiClient.post('/api/settings/calibrate');
      setSuccess('Calibration completed: ' + (res.data?.message || 'OK'));
      setTimeout(() => setSuccess(null), 5000);
      // Refresh settings & engine config after calibration
      const fresh = await apiClient.get('/api/settings');
      setSettings(fresh.data);
      loadEngineConfig();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Calibration failed');
    } finally {
      setCalibrating(false);
      setShowCalibrateConfirm(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        professor_profile: settings.professor_profile || DEFAULT_PROFILE,
        engine_weights: settings.engine_weights,
        default_threshold: settings.default_threshold,
        openai_api_key: settings.openai_api_key,
        openai_base_url: settings.openai_base_url,
        openai_model: settings.openai_model,
        anthropic_api_key: settings.anthropic_api_key,
        anthropic_model: settings.anthropic_model,
        moss_user_id: settings.moss_user_id,
        embedding_runtime: settings.embedding_runtime,
        embedding_model: settings.embedding_model,
        embedding_server_url: settings.embedding_server_url,
        embedding_server_host: settings.embedding_server_host,
        embedding_server_port: settings.embedding_server_port,
        embedding_device: settings.embedding_device,
        embedding_batch_size: settings.embedding_batch_size,
        batch_size: settings.batch_size,
        max_file_size_mb: settings.max_file_size_mb,
        max_files_per_job: settings.max_files_per_job,
        webhook_url: webhookUrl,
        source_scan_enabled: Boolean(settings.source_scan_enabled),
        source_scan_sites: settings.source_scan_sites || [],
        audit_log_level: settings.audit_log_level,
        audit_retention_days: settings.audit_retention_days,
        debug_mode: settings.debug_mode,
      };
      await apiClient.patch('/api/settings', payload);
      const fresh = await apiClient.get('/api/settings');
      setSettings(fresh.data);
      setSuccess('Settings saved. Recommended profile applied.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (authLoading || !settings) {
    return (
      <DashboardLayout requiredRole="admin">
        <div className="flex h-64 items-center justify-center px-4 py-8 text-slate-500">Loading settings...</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout requiredRole="admin">
      <div className="max-w-none space-y-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        {/* Header */}
        <PageHeader
          eyebrow="Settings"
          title="Professor-friendly detection settings"
          description="Keep the default profile for everyday use. IntegrityDesk detects assignment shape, calibrates thresholds, and suppresses common false positives automatically."
          action={
            <button
              type="button"
              onClick={saveSettings}
              disabled={saving}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
            >
              <Save size={16} />
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          }
          eyebrowStyle="badge"
        />

        {/* Notifications */}
        {error && <Notice tone="red" icon={AlertTriangle}>{error}</Notice>}
        {success && <Notice tone="green" icon={Shield}>{success}</Notice>}

        {/* Main Tab Navigation */}
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Settings Categories</div>
        <div className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-sm mb-6">
          {MAIN_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`inline-flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold transition ${activeTab === tab.id
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/15'
                : 'text-slate-600 hover:bg-slate-50'
                }`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content - All sections shown per category */}
        <div className="space-y-8">
          {/* DETECTION SETTINGS */}
          {activeTab === 'detection' && (
            <div className="space-y-6">
              {/* Detection Overview */}
              <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <Cpu size={20} className="mt-0.5 shrink-0 text-slate-600" />
                  <div className="flex-1">
                    <h2 className="text-lg font-semibold text-slate-950">Detection Engines Overview</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      IntegrityDesk uses 8 detection engines operating simultaneously. Each engine scores submission pairs independently, then a fusion layer combines them into a single confidence score.
                    </p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {[
                    { name: 'Token', desc: 'Identifier & literal normalization' },
                    { name: 'Winnowing', desc: 'Fingerprint hashing' },
                    { name: 'GST', desc: 'Greedy string tiling' },
                    { name: 'AST', desc: 'Abstract syntax tree' },
                    { name: 'N-Gram', desc: 'N-gram frequency analysis' },
                    { name: 'Graph', desc: 'Control/data flow graphs' },
                    { name: 'Embedding', desc: 'Code vector similarity' },
                    { name: 'Static Rules', desc: 'Heuristic pattern rules' },
                  ].map((engine) => (
                    <div key={engine.name} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5 text-center">
                      <div className="text-xs font-semibold text-slate-800">{engine.name}</div>
                      <div className="mt-0.5 text-[10px] leading-tight text-slate-500">{engine.desc}</div>
                    </div>
                  ))}
                </div>
              </section>

              {/* Default Threshold card */}
              <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <Target size={20} className="mt-0.5 shrink-0 text-slate-600" />
                  <div className="flex-1">
                    <h2 className="text-lg font-semibold text-slate-950">Default Similarity Threshold</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      Sets the minimum score for flagging a pair as suspicious. Lower thresholds catch more but increase false positives.
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
                      value={settings.default_threshold ?? 0.82}
                      onChange={(event) => updateSetting('default_threshold', Number(event.target.value))}
                      className="flex-1 accent-blue-600"
                    />
                    <div className="min-w-[5rem] text-right">
                      <span className="text-2xl font-bold text-blue-600">{((settings.default_threshold ?? 0.82) * 100).toFixed(0)}%</span>
                      <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Cutoff</div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${(settings.default_threshold ?? 0.82) >= 0.8 ? 'bg-red-100 text-red-700' : (settings.default_threshold ?? 0.82) >= 0.7 ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'}`}>
                      {(settings.default_threshold ?? 0.82) >= 0.8 ? 'Conservative' : (settings.default_threshold ?? 0.82) >= 0.7 ? 'Balanced' : 'Lenient'}
                    </span>
                    <span className="text-xs text-slate-500 leading-6">This is the default for new jobs. Can be overridden per-job.</span>
                  </div>
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
                  <TextInput label="Max File Size (MB)" type="number" value={settings.max_file_size_mb} onChange={(value) => updateSetting('max_file_size_mb', Number(value))} />
                  <TextInput label="Max Files Per Job" type="number" value={settings.max_files_per_job} onChange={(value) => updateSetting('max_files_per_job', Number(value))} />
                  <TextInput label="Processing Batch Size" type="number" value={settings.batch_size} onChange={(value) => updateSetting('batch_size', Number(value))} />
                </div>
                <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-600">
                  <strong className="font-semibold">Tip:</strong> For large classes (&gt;100 students), increase batch size to 50-100 for faster processing. Reduce max file size if submissions contain large data files or binaries.
                </div>
              </Accordion>

              {/* Engine Weights - Advanced */}
              <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
                <div
                  className="flex cursor-pointer items-center justify-between"
                  onClick={() => setShowEngineWeights(!showEngineWeights)}
                >
                  <div className="flex items-center gap-2">
                    <Activity size={16} className="text-amber-700" />
                    <span className="text-sm font-semibold text-amber-900">Advanced: Engine Weights</span>
                  </div>
                  <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-800">Admin</span>
                </div>
                <p className="mt-2 text-sm leading-5 text-amber-700">
                  Fine-tune the contribution of each detection engine. For administrators validating custom presets only.
                </p>

                {showEngineWeights && (
                  <div className="mt-4 space-y-3 border-t border-amber-300/50 pt-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-semibold text-amber-900">Total allocation</span>
                      <span className={`font-bold ${Math.abs(engineWeightTotal - 1.0) < 0.001 ? 'text-emerald-700' : 'text-red-600'}`}>
                        {(engineWeightTotal * 100).toFixed(0)}%
                      </span>
                    </div>
                    {Object.entries(settings.engine_weights || {}).map(([key, value]) => (
                      <AdvancedSlider
                        key={key}
                        label={key}
                        value={Number(value || 0)}
                        onChange={(next) => updateSetting('engine_weights', { ...settings.engine_weights, [key]: next })}
                      />
                    ))}
                    {Math.abs(engineWeightTotal - 1.0) >= 0.001 && (
                      <div className="rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-700">
                        Weights should sum to 100% (currently {(engineWeightTotal * 100).toFixed(0)}%). Adjust sliders to balance.
                      </div>
                    )}
                  </div>
                )}
              </section>
            </div>
          )}

          {/* AI & EVIDENCE */}
          {activeTab === 'intelligence' && (
            <div className="space-y-6">
              {/* AI Providers Summary */}
              <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <Bot size={20} className="mt-0.5 shrink-0 text-slate-600" />
                  <div className="flex-1">
                    <h2 className="text-lg font-semibold text-slate-950">AI Provider Integration</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      Connect AI services for enhanced detection capabilities - AI-assisted rewrite analysis, code explanation generation, and evidence summarization.
                    </p>
                  </div>
                </div>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  {/* OpenAI Card */}
                  <div className="rounded-xl border border-slate-200 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`h-2.5 w-2.5 rounded-full ${settings.openai_api_key_configured ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                        <span className="text-sm font-semibold text-slate-900">OpenAI</span>
                      </div>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${settings.openai_api_key_configured ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                        {settings.openai_api_key_configured ? 'Connected' : 'Not configured'}
                      </span>
                    </div>
                    <div className="mt-3 space-y-3">
                      <TextInput label="API Key" type="password" value={settings.openai_api_key} placeholder={settings.openai_api_key_configured ? 'Leave blank to keep current key' : 'Enter OpenAI API key'} onChange={(value) => updateSetting('openai_api_key', value)} />
                      <div className="grid grid-cols-2 gap-3">
                        <TextInput label="Base URL" value={settings.openai_base_url} onChange={(value) => updateSetting('openai_base_url', value)} />
                        <TextInput label="Model" value={settings.openai_model} onChange={(value) => updateSetting('openai_model', value)} />
                      </div>
                    </div>
                  </div>
                  {/* Anthropic Card */}
                  <div className="rounded-xl border border-slate-200 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`h-2.5 w-2.5 rounded-full ${settings.anthropic_api_key_configured ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                        <span className="text-sm font-semibold text-slate-900">Anthropic</span>
                      </div>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${settings.anthropic_api_key_configured ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                        {settings.anthropic_api_key_configured ? 'Connected' : 'Not configured'}
                      </span>
                    </div>
                    <div className="mt-3 space-y-3">
                      <TextInput label="API Key" type="password" value={settings.anthropic_api_key} placeholder={settings.anthropic_api_key_configured ? 'Leave blank to keep current key' : 'Enter Anthropic API key'} onChange={(value) => updateSetting('anthropic_api_key', value)} />
                      <TextInput label="Model" value={settings.anthropic_model} onChange={(value) => updateSetting('anthropic_model', value)} />
                    </div>
                  </div>
                </div>
                <div className="mt-3 rounded-lg bg-blue-50 p-3 text-xs leading-5 text-blue-700">
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
                  <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-4">
                    <input
                      type="checkbox"
                      checked={Boolean(settings.source_scan_enabled)}
                      onChange={(event) => updateSetting('source_scan_enabled', event.target.checked)}
                      className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600"
                    />
                    <span>
                      <span className="block text-sm font-semibold text-slate-950">Enable public source scanning</span>
                      <span className="mt-1 block text-sm leading-6 text-slate-500">When enabled, each submission is compared against configured public code repositories and URLs.</span>
                    </span>
                  </label>

                  {settings.source_scan_enabled && (
                    <>
                      <div className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800">
                        <span className="font-semibold">Status:</span> Public scanning is active. Add URLs below for repositories to scan.
                        {settings.source_scan_sites?.length > 0 && (
                          <span className="block mt-1">Currently tracking <strong>{settings.source_scan_sites.length}</strong> source{settings.source_scan_sites.length !== 1 ? 's' : ''}.</span>
                        )}
                      </div>
                      <TextAreaInput
                        label="Source URLs (one per line)"
                        value={(settings.source_scan_sites || []).join('\n')}
                        placeholder={'https://github.com/org/course-solutions\nhttps://raw.githubusercontent.com/org/repo/main/solution.py\nhttps://pastebin.com/raw/abc123'}
                        onChange={(value) => updateSetting('source_scan_sites', value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                      />
                    </>
                  )}

                  {!settings.source_scan_enabled && (
                    <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">
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
                  <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                    MOSS (Measure Of Software Similarity) is a legacy tool from Stanford. It provides an additional cross-reference for large classes.
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={`h-2.5 w-2.5 rounded-full ${settings.moss_user_id_configured ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                    <span className={`text-xs font-semibold ${settings.moss_user_id_configured ? 'text-emerald-700' : 'text-slate-500'}`}>
                      {settings.moss_user_id_configured ? 'MOSS configured' : 'MOSS not configured'}
                    </span>
                  </div>
                  <TextInput label="MOSS User ID" type="password" value={settings.moss_user_id} placeholder={settings.moss_user_id_configured ? 'Leave blank to keep current MOSS user ID' : 'Enter MOSS user ID'} onChange={(value) => updateSetting('moss_user_id', value)} />
                </div>
              </Accordion>
            </div>
          )}

          {/* REVIEW & WORKFLOW */}
          {activeTab === 'workflow' && (
            <div className="space-y-6">
              {/* Assignment Type */}
              <SettingsGroup
                title="Assignment Type"
                description="Auto Detect is recommended. It automatically chooses the right rules based on your assignment language, size, notebooks, starter code, and tests."
                icon={GitMerge}
              >
                <OptionGrid
                  options={catalog.assignment_types || []}
                  value={profile.assignment_type}
                  onChange={(value) => updateProfile('assignment_type', value)}
                />
              </SettingsGroup>

              {/* Sensitivity & Detection Profile */}
              <SettingsGroup
                title="Sensitivity & Threshold"
                description="How aggressively should the system flag submissions? Conservative has fewer false positives; Strict catches more cases."
                icon={Target}
              >
                <SegmentedOptions
                  options={catalog.sensitivities || catalog.review_modes || []}
                  value={profile.sensitivity}
                  onChange={(value) => updateProfile('sensitivity', value)}
                />
                <div className="mt-4 rounded-lg bg-blue-50 p-3 text-sm text-blue-700">
                  <span className="font-semibold">Current threshold: </span>
                  {profile.sensitivity === 'conservative' && '\u226584% similarity - best for formal investigations'}
                  {profile.sensitivity === 'balanced' && '\u226575% similarity - recommended default'}
                  {profile.sensitivity === 'strict' && '\u226564% similarity - shows more cases for early triage'}
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
                <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm leading-6 text-slate-600">
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
                <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm leading-6 text-slate-600">
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
                <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm leading-6 text-slate-600">
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

              {/* External Source Scan checkbox */}
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={Boolean(profile.external_source_scan)}
                    onChange={(event) => updateProfile('external_source_scan', event.target.checked)}
                    className="mt-1 h-4 w-4 rounded border-slate-300 text-emerald-600"
                  />
                  <span>
                    <span className="block text-sm font-semibold text-slate-950">Enable external / public source scan</span>
                    <span className="mt-1 block text-sm leading-6 text-slate-500">Scan configured GitHub repos and websites (from AI & Evidence section) when running checks.</span>
                  </span>
                </label>
              </div>

              {/* Applied Profile Summary + Policy Details */}
              <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
                <div className="space-y-6">
                  <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="text-sm font-semibold text-slate-950">Active Profile Summary</div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{applied.recommendation}</p>
                    <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm font-medium text-slate-950">
                      {applied.summary}
                    </div>

                    {/* Detection Policy Details */}
                    <div className="mt-5 space-y-2 border-t border-slate-100 pt-4">
                      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Derived Detection Policy</div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
                          <span className="text-xs font-semibold text-slate-500">Threshold</span>
                          <div className="font-semibold text-slate-900">{(applied.threshold * 100)?.toFixed(0) || '-'}%</div>
                        </div>
                        <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
                          <span className="text-xs font-semibold text-slate-500">Result Limit</span>
                          <div className="font-semibold text-slate-900">{applied.result_limit ?? 'All'}</div>
                        </div>
                        <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5 col-span-2">
                          <span className="text-xs font-semibold text-slate-500">Weights</span>
                          <div className="mt-1 flex flex-wrap gap-1.5">
                            {Object.entries(applied.weights || {}).map(([key, value]) => (
                              <span key={key} className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                                {key}: {((value as number) * 100).toFixed(0)}%
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </section>

                  {applied.warnings?.length > 0 && (
                    <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
                      {applied.warnings.map((warning: string) => <div key={warning}>{warning}</div>)}
                    </section>
                  )}
                </div>

                <aside className="space-y-6">
                  <section className="rounded-xl border border-blue-200 bg-blue-50 p-5">
                    <div className="text-sm font-semibold text-blue-950">System handles automatically</div>
                    <div className="mt-3 space-y-2 text-sm leading-6 text-blue-800">
                      <div>{'\u2022'} Starter code is excluded from comparisons</div>
                      <div>{'\u2022'} Previous-term submissions are matched when available</div>
                      <div>{'\u2022'} Runtime behavior and identical wrong answers are compared</div>
                      <div>{'\u2022'} Thresholds are automatically adjusted</div>
                    </div>
                  </section>

                  <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="text-sm font-semibold text-slate-950">Profile Quick Stats</div>
                    <div className="mt-3 space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600">Assignment Type</span>
                        <span className="font-semibold text-slate-900 capitalize">{profile.assignment_type?.replace(/_/g, ' ') || 'Auto'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600">Sensitivity</span>
                        <span className="font-semibold text-slate-900">{profile.sensitivity?.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()) || 'Balanced'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600">AI Rewrite Detection</span>
                        <span className="font-semibold text-slate-900">{profile.ai_rewrite_detection?.replace(/\b\w/g, (l: string) => l.toUpperCase()) || 'Balanced'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600">Starter Code</span>
                        <span className="font-semibold text-slate-900 text-right max-w-[180px]">{profile.starter_code_handling?.replace(/_/g, ' ') || 'Student-written only'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600">Previous Terms</span>
                        <span className="font-semibold text-slate-900 text-right max-w-[180px]">{profile.previous_term_matching?.replace(/_/g, ' ') || 'Same course only'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600">Results Per Job</span>
                        <span className="font-semibold text-slate-900">{profile.result_volume?.replace(/_/g, ' ').replace('top ', 'Top ') || 'Top 25'}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600">External Scan</span>
                        <span className={`font-semibold ${profile.external_source_scan ? 'text-emerald-600' : 'text-slate-400'}`}>
                          {profile.external_source_scan ? 'Enabled' : 'Disabled'}
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
              <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-start gap-3">
                  <Database size={20} className="mt-0.5 shrink-0 text-slate-600" />
                  <div className="flex-1">
                    <h2 className="text-lg font-semibold text-slate-950">Database & System Health</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600">Current connection status and system information.</p>
                  </div>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-emerald-700">Database</div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
                      <span className="text-sm font-medium text-emerald-900">Connected</span>
                    </div>
                    <div className="mt-1 text-xs text-emerald-600">Neon PostgreSQL</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-600">Default Threshold</div>
                    <div className="mt-1 text-sm font-medium text-slate-900">{(Number(settings.default_threshold || 0.82) * 100).toFixed(0)}%</div>
                    <div className="mt-1 text-xs text-slate-500">Similarity cutoff</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-600">Debug Mode</div>
                    <div className="mt-1 text-sm font-medium text-slate-900">
                      {settings.debug_mode ? (
                        <span className="text-amber-600">Enabled</span>
                      ) : (
                        <span className="text-slate-600">Disabled</span>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">Verbose logging</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-600">Embedding Runtime</div>
                    <div className="mt-1 text-sm font-medium text-slate-900 capitalize">{settings.embedding_runtime?.replace(/_/g, ' ') || 'Local'}</div>
                    <div className="mt-1 text-xs text-slate-500">{settings.embedding_model || 'UniXcoder'}</div>
                  </div>
                </div>
              </section>

              {/* Detection Threshold */}
              <Accordion
                title="Detection Threshold"
                description="Set the default similarity threshold for flagging submissions. Lower values catch more but may increase false positives."
                isOpen={accordions.detectionThreshold}
                onToggle={() => setAccordions(prev => ({ ...prev, detectionThreshold: !prev.detectionThreshold }))}
              >
                <div className="space-y-4">
                  <div className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800">
                    This threshold is used as the default for new jobs. You can override it per-job from the upload page.
                  </div>
                  <label className="block">
                    <span className="text-sm font-medium text-slate-700">Default Similarity Threshold</span>
                    <div className="mt-2 flex items-center gap-4">
                      <input
                        type="range"
                        min="0.5"
                        max="1.0"
                        step="0.01"
                        value={settings.default_threshold ?? 0.82}
                        onChange={(event) => updateSetting('default_threshold', Number(event.target.value))}
                        className="flex-1 accent-blue-600"
                      />
                      <span className="min-w-[4rem] text-right text-sm font-semibold text-blue-600">
                        {((settings.default_threshold ?? 0.82) * 100).toFixed(0)}%
                      </span>
                    </div>
                  </label>
                </div>
              </Accordion>

              {/* Webhooks */}
              <Accordion
                title="Webhooks"
                description="Configure webhooks for real-time notifications when jobs complete or flag high-risk submissions."
                isOpen={accordions.webhooks}
                onToggle={() => setAccordions(prev => ({ ...prev, webhooks: !prev.webhooks }))}
              >
                <TextInput label="Webhook URL" value={webhookUrl} onChange={setWebhookUrl} placeholder="https://example.com/webhook" />
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
                  <TextInput label="Audit Retention (days)" type="number" value={settings.audit_retention_days ?? 365} onChange={(value) => updateSetting('audit_retention_days', Number(value))} />
                </div>
                <div className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                  Audit logs older than the retention period may be automatically pruned. Keep a minimum of 90 days for compliance.
                </div>
              </Accordion>

              {/* Configuration Validation */}
              <Accordion
                title="Configuration Validation"
                description="Validate the current engine configuration for issues like weight sum, threshold ranges, and governance."
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
                    {validationLoading ? 'Validating...' : 'Run Validation'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { loadEngineConfig(); setAccordions(prev => ({ ...prev, configValidation: true })); }}
                    disabled={configLoading}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
                  >
                    {configLoading ? <Loader2 size={16} className="animate-spin" /> : <FileCog size={16} />}
                    {configLoading ? 'Loading...' : 'View Engine Config'}
                  </button>
                </div>

{validationResult.issues && (
                  <div className="mt-4 space-y-2">
                    {validationResult.issues.length > 0 ? (
                      validationResult.issues.map((issue: string, i: number) => (
                        <div key={i} className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                          <XCircle size={16} className="mt-0.5 shrink-0" />
                          <span>{issue}</span>
                        </div>
                      ))
                    ) : (
                      <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
                        <CheckCircle size={16} className="mt-0.5 shrink-0" />
                        <span>Configuration looks healthy. No issues detected.</span>
                      </div>
                    )}
                  </div>
                )}

                {engineConfig && (
                  <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-3 text-sm font-semibold text-slate-800">Current Engine Configuration</div>
                    <pre className="max-h-64 overflow-auto rounded bg-slate-800 p-3 text-xs text-green-300">{JSON.stringify(engineConfig, null, 2)}</pre>
                  </div>
                )}
              </Accordion>

              {/* Calibrate Engine */}
              <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                      <Activity size={16} />
                      Automatic Engine Calibration
                    </div>
                    <p className="mt-1 text-sm leading-6 text-amber-700">
                      Automatically tune engine weights based on known labeled data. This will adjust the detection profile to maximize F1 score on past validated pairs.
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
                        className="rounded-lg border border-amber-300 bg-white px-4 py-2 text-sm font-semibold text-amber-800 transition hover:bg-amber-100"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setShowCalibrateConfirm(true)}
                      className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-700"
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
                className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-4 py-2.5 text-left text-sm font-semibold text-slate-700 hover:bg-slate-100"
              >
                <span className="flex items-center gap-2">
                  <Zap size={16} />
                  Advanced: Embedding & Resource Settings
                </span>
                <span>{accordions.embeddingAdvanced ? 'Hide' : 'Show'}</span>
              </button>

              {accordions.embeddingAdvanced && (
                <div className="space-y-4">
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                    These settings control how the system processes and compares code submissions. Changes take effect immediately.
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    <SelectInput label="Embedding Runtime" value={settings.embedding_runtime} options={[['local_unixcoder', 'Local (UniXcoder)'], ['remote_openai_compatible', 'Remote Server']]} onChange={(value) => updateSetting('embedding_runtime', value)} />
                    <TextInput label="Embedding Model" value={settings.embedding_model || ''} placeholder="e.g. microsoft/unixcoder-base" onChange={(value) => updateSetting('embedding_model', value)} />
                    <SelectInput label="Hardware Acceleration" value={settings.embedding_device} options={[['auto', 'Auto'], ['cuda', 'CUDA / GPU'], ['cpu', 'CPU only']]} onChange={(value) => updateSetting('embedding_device', value)} />
                    <TextInput label="Embedding Batch Size" type="number" value={settings.embedding_batch_size} onChange={(value) => updateSetting('embedding_batch_size', Number(value))} />
                    <TextInput label="Embedding Server URL" value={settings.embedding_server_url || ''} placeholder="http://127.0.0.1:8001/v1" onChange={(value) => updateSetting('embedding_server_url', value)} />
                    <TextInput label="Embedding Server Port" type="number" value={settings.embedding_server_port} onChange={(value) => updateSetting('embedding_server_port', Number(value))} />
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
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-5 py-4 text-left transition-colors hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-blue-200 rounded-t-xl"
      >
        <div>
          <div className="text-lg font-semibold text-slate-950">{title}</div>
          {description && (
            <div className="mt-1 text-sm leading-6 text-slate-600">{description}</div>
          )}
        </div>
        <ChevronDown
          size={20}
          className={`text-slate-400 transition-transform ${isOpen ? 'rotate-180 text-blue-600' : ''}`}
        />
      </button>
      {isOpen && (
        <div className="border-t border-slate-200 px-5 pb-5 pt-4 transition-all duration-200">
          {children}
        </div>
      )}
    </div>
  );
}

function SettingsGroup({ title, description, children, icon: Icon }: { title: string; description: string; children: React.ReactNode; icon?: React.ElementType }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start gap-3">
        {Icon && <Icon size={20} className="mt-0.5 shrink-0 text-slate-600" />}
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
        </div>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function OptionGrid({ options, value, onChange }: { options: { id: string; label: string; description: string }[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          onClick={() => onChange(option.id)}
          className={`rounded-xl border p-4 text-left transition ${value === option.id ? 'border-blue-300 bg-blue-50 ring-2 ring-blue-100' : 'border-slate-200 hover:bg-slate-50'
            }`}
        >
          <div className="text-sm font-semibold text-slate-950">{option.label}</div>
          <div className="mt-1 text-sm leading-5 text-slate-500">{option.description}</div>
        </button>
      ))}
    </div>
  );
}

function SegmentedOptions({ options, value, onChange }: { options: { id: string; label: string }[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          onClick={() => onChange(option.id)}
          className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${value === option.id ? 'bg-blue-600 text-white' : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
            }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function AdvancedSlider({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm font-semibold capitalize text-slate-950">{label.replaceAll('_', ' ')}</div>
        <div className="text-sm font-semibold text-blue-600">{Math.round(value * 100)}%</div>
      </div>
      <input type="range" min="0" max="1" step="0.05" value={value} onChange={(event) => onChange(Number(event.target.value))} className="w-full accent-blue-600" />
    </div>
  );
}

function TextInput({ label, value, onChange, type = 'text', placeholder = '' }: { label: string; value: string | number; onChange: (value: string) => void; type?: string; placeholder?: string }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        type={type}
        value={value ?? ''}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 h-11 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-50"
      />
    </label>
  );
}

function TextAreaInput({ label, value, onChange, placeholder = '' }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <textarea
        value={value ?? ''}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        rows={5}
        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-50"
      />
    </label>
  );
}

function SelectInput({ label, value, options, onChange }: { label: string; value: string; options: [string, string][]; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <select
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 h-11 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-50"
      >
        {options.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
      </select>
    </label>
  );
}

function Notice({ children, tone, icon: Icon }: { children: React.ReactNode; tone: 'red' | 'green'; icon: React.ElementType }) {
  const className = tone === 'red'
    ? 'border-red-200 bg-red-50 text-red-700'
    : 'border-emerald-200 bg-emerald-50 text-emerald-700';
  return (
    <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${className}`}>
      <Icon size={16} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </div>
  );
}