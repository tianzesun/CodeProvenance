// @ts-nocheck
'use client';

import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { AlertTriangle, ChevronDown, Save, Shield, SlidersHorizontal } from 'lucide-react';

const DEFAULT_PROFILE = {
  assignment_type: 'auto_detect',
  sensitivity: 'balanced',
  starter_code_handling: 'student_written_only',
  previous_term_matching: 'same_course_only',
  ai_rewrite_detection: 'balanced',
  result_volume: 'top_25',
};

const ADVANCED_TABS = ['Engine weights', 'Integrations', 'Performance'];

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [settings, setSettings] = useState(null);
  const [activeAdvanced, setActiveAdvanced] = useState('Engine weights');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (authLoading || !user) return;
    axios.get('/api/settings')
      .then((res) => setSettings(res.data))
      .catch(() => setError('Failed to load settings'));
  }, [authLoading, user]);

  const profile = settings?.professor_profile || DEFAULT_PROFILE;
  const catalog = settings?.professor_profile_catalog || {};
  const applied = settings?.applied_professor_profile || {};
  const engineWeightTotal = useMemo(
    () => Object.values(settings?.engine_weights || {}).reduce((sum, weight) => sum + Number(weight || 0), 0),
    [settings?.engine_weights],
  );

  const updateSetting = (key, value) => {
    setSettings((current) => ({ ...current, [key]: value }));
  };

  const updateProfile = (key, value) => {
    setSettings((current) => ({
      ...current,
      professor_profile: {
        ...(current?.professor_profile || DEFAULT_PROFILE),
        [key]: value,
      },
    }));
  };

  const saveSettings = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        professor_profile: settings.professor_profile || DEFAULT_PROFILE,
        engine_weights: settings.engine_weights,
        openai_api_key: settings.openai_api_key,
        openai_base_url: settings.openai_base_url,
        openai_model: settings.openai_model,
        anthropic_api_key: settings.anthropic_api_key,
        anthropic_model: settings.anthropic_model,
        moss_user_id: settings.moss_user_id,
        embedding_runtime: settings.embedding_runtime,
        embedding_model: settings.embedding_model,
        embedding_server_host: settings.embedding_server_host,
        embedding_server_port: settings.embedding_server_port,
        embedding_device: settings.embedding_device,
        embedding_batch_size: settings.embedding_batch_size,
        batch_size: settings.batch_size,
        max_file_size_mb: settings.max_file_size_mb,
        max_files_per_job: settings.max_files_per_job,
      };
      await axios.patch('/api/settings', payload);
      const fresh = await axios.get('/api/settings');
      setSettings(fresh.data);
      setSuccess('Settings saved. Recommended profile applied.');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
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
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="text-sm font-medium text-slate-500">Settings</div>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Professor-friendly detection settings</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
                Keep the default profile for everyday use. IntegrityDesk detects assignment shape, calibrates thresholds, and suppresses common false positives automatically.
              </p>
            </div>
            <button
              type="button"
              onClick={saveSettings}
              disabled={saving}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
            >
              <Save size={16} />
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </section>

        {error && <Notice tone="red" icon={AlertTriangle}>{error}</Notice>}
        {success && <Notice tone="green" icon={Shield}>{success}</Notice>}

        <section className="grid gap-6 xl:grid-cols-[1fr_360px]">
          <div className="space-y-6">
            <SettingsGroup
              title="Detection Profile"
              description="Auto Detect is recommended. It chooses the right assignment profile from language, file count, code shape, notebooks, starter code, and tests."
            >
              <OptionGrid
                options={catalog.assignment_types || []}
                value={profile.assignment_type}
                onChange={(value) => updateProfile('assignment_type', value)}
              />
            </SettingsGroup>

            <SettingsGroup
              title="Review Mode"
              description="Use Conservative for formal investigations, Balanced for everyday review, and Strict for broader triage."
            >
              <SegmentedOptions
                options={catalog.review_modes || catalog.sensitivities || []}
                value={profile.sensitivity}
                onChange={(value) => updateProfile('sensitivity', value)}
              />
            </SettingsGroup>

            <SettingsGroup title="Result Size" description="Top 25 is the recommended review queue size for most assignments.">
              <SegmentedOptions
                options={catalog.result_volume || []}
                value={profile.result_volume}
                onChange={(value) => updateProfile('result_volume', value)}
              />
            </SettingsGroup>
          </div>

          <aside className="space-y-6">
            <section className="rounded-xl border border-blue-200 bg-blue-50 p-5">
              <div className="text-sm font-semibold text-blue-950">Recommended profile applied</div>
              <p className="mt-3 text-sm leading-6 text-blue-800">{applied.recommendation}</p>
              <div className="mt-4 rounded-lg bg-white/70 p-3 text-sm font-medium text-blue-950">
                {applied.summary}
              </div>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-sm font-semibold text-slate-950">Automatically handled</div>
              <div className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
                <div>Starter code removed before comparison.</div>
                <div>Previous-term matching enabled when history is available.</div>
                <div>Runtime behavior and same wrong answers compared.</div>
                <div>Thresholds calibrated per assignment using outliers, score gaps, and rare evidence.</div>
              </div>
            </section>

            {applied.warnings?.length > 0 && (
              <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
                {applied.warnings.map((warning) => <div key={warning}>{warning}</div>)}
              </section>
            )}
          </aside>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <button
            type="button"
            onClick={() => setAdvancedOpen((value) => !value)}
            className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
          >
            <span className="inline-flex items-center gap-3 text-lg font-semibold text-slate-950">
              <SlidersHorizontal size={18} />
              Advanced Settings
            </span>
            <ChevronDown size={18} className={`transition ${advancedOpen ? 'rotate-180' : ''}`} />
          </button>

          {advancedOpen && (
            <div className="border-t border-slate-200 p-5">
              <div className="mb-5 flex flex-wrap gap-2">
                {ADVANCED_TABS.map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setActiveAdvanced(tab)}
                    className={`rounded-lg px-3 py-2 text-sm font-semibold ${
                      activeAdvanced === tab ? 'bg-blue-600 text-white' : 'border border-slate-200 text-slate-600'
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              {activeAdvanced === 'Engine weights' && (
                <div className="space-y-4">
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                    Engine weights are for administrators validating custom presets. Normal professors should use the simple profile above.
                  </div>
                  <div className="text-sm font-semibold text-slate-950">Total: {(engineWeightTotal * 100).toFixed(0)}%</div>
                  {Object.entries(settings.engine_weights || {}).map(([key, value]) => (
                    <AdvancedSlider
                      key={key}
                      label={key}
                      value={Number(value || 0)}
                      onChange={(next) => updateSetting('engine_weights', { ...settings.engine_weights, [key]: next })}
                    />
                  ))}
                </div>
              )}

              {activeAdvanced === 'Integrations' && (
                <div className="grid gap-4 md:grid-cols-2">
                  <TextInput label="OpenAI API Key" type="password" value={settings.openai_api_key} placeholder={settings.openai_api_key_configured ? 'Leave blank to keep current key' : 'Enter OpenAI API key'} onChange={(value) => updateSetting('openai_api_key', value)} />
                  <TextInput label="OpenAI Base URL" value={settings.openai_base_url} onChange={(value) => updateSetting('openai_base_url', value)} />
                  <TextInput label="OpenAI Model" value={settings.openai_model} onChange={(value) => updateSetting('openai_model', value)} />
                  <TextInput label="Anthropic API Key" type="password" value={settings.anthropic_api_key} placeholder={settings.anthropic_api_key_configured ? 'Leave blank to keep current key' : 'Enter Anthropic API key'} onChange={(value) => updateSetting('anthropic_api_key', value)} />
                  <TextInput label="Anthropic Model" value={settings.anthropic_model} onChange={(value) => updateSetting('anthropic_model', value)} />
                  <TextInput label="MOSS User ID" type="password" value={settings.moss_user_id} placeholder={settings.moss_user_id_configured ? 'Leave blank to keep current MOSS user ID' : 'Enter MOSS user ID'} onChange={(value) => updateSetting('moss_user_id', value)} />
                </div>
              )}

              {activeAdvanced === 'Performance' && (
                <div className="grid gap-4 md:grid-cols-3">
                  <SelectInput label="Embedding Runtime" value={settings.embedding_runtime} options={[['local_unixcoder', 'Local UniXcoder'], ['remote_openai_compatible', 'Remote OpenAI-Compatible Server']]} onChange={(value) => updateSetting('embedding_runtime', value)} />
                  <SelectInput label="Embedding Device" value={settings.embedding_device} options={[['auto', 'Auto'], ['cuda', 'CUDA / GPU'], ['cpu', 'CPU']]} onChange={(value) => updateSetting('embedding_device', value)} />
                  <TextInput label="Embedding Batch Size" type="number" value={settings.embedding_batch_size} onChange={(value) => updateSetting('embedding_batch_size', Number(value))} />
                  <TextInput label="Maximum File Size MB" type="number" value={settings.max_file_size_mb} onChange={(value) => updateSetting('max_file_size_mb', Number(value))} />
                  <TextInput label="Maximum Files Per Job" type="number" value={settings.max_files_per_job} onChange={(value) => updateSetting('max_files_per_job', Number(value))} />
                  <TextInput label="Processing Batch Size" type="number" value={settings.batch_size} onChange={(value) => updateSetting('batch_size', Number(value))} />
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}

function SettingsGroup({ title, description, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function OptionGrid({ options, value, onChange }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          onClick={() => onChange(option.id)}
          className={`rounded-xl border p-4 text-left transition ${
            value === option.id ? 'border-blue-300 bg-blue-50 ring-2 ring-blue-100' : 'border-slate-200 hover:bg-slate-50'
          }`}
        >
          <div className="text-sm font-semibold text-slate-950">{option.label}</div>
          <div className="mt-1 text-sm leading-5 text-slate-500">{option.description}</div>
        </button>
      ))}
    </div>
  );
}

function SegmentedOptions({ options, value, onChange }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          onClick={() => onChange(option.id)}
          className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${
            value === option.id ? 'bg-blue-600 text-white' : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function AdvancedSlider({ label, value, onChange }) {
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

function TextInput({ label, value, onChange, type = 'text', placeholder = '' }) {
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

function SelectInput({ label, value, options, onChange }) {
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

function Notice({ children, tone, icon: Icon }) {
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
