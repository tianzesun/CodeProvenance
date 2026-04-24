"use client";

import { useState, useEffect } from "react";
import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import axios from "axios";
import { Settings, Cpu, Zap, Shield, Database, AlertTriangle } from 'lucide-react';

const ENGINE_CATALOG = [
  { key: "token", label: "Token", tier: "core", description: "Token-level overlap and lexical similarity." },
  { key: "ast", label: "AST", tier: "core", description: "Structural similarity across parsed syntax trees." },
  { key: "winnowing", label: "Winnowing", tier: "core", description: "K-gram fingerprinting for copy-paste style matches." },
  { key: "gst", label: "GST", tier: "core", description: "Greedy String Tiling for long contiguous match blocks." },
  { key: "semantic", label: "Semantic", tier: "core", description: "Meaning-level similarity via embedding analysis." },
  { key: "web", label: "Web", tier: "core", description: "External-source similarity checks against web-accessible code." },
];

const DEFAULT_ENGINE_WEIGHTS = {
  token: 0.18,
  ast: 0.22,
  winnowing: 0.16,
  gst: 0.16,
  semantic: 0.18,
  web: 0.10,
};

interface Settings {
  default_threshold: number;
  openai_api_key: string;
  openai_api_key_configured: boolean;
  openai_base_url: string;
  openai_model: string;
  anthropic_api_key: string;
  anthropic_api_key_configured: boolean;
  anthropic_model: string;
  moss_user_id: string;
  moss_user_id_configured: boolean;
  embedding_runtime: string;
  embedding_model: string;
  embedding_server_host: string | null;
  embedding_server_port: number;
  embedding_device: string;
  embedding_batch_size: number;
  engine_weights: { [key: string]: number };
  batch_size: number;
  max_file_size_mb: number;
  max_files_per_job: number;
}

type SettingsTab = "general" | "detection_engines" | "ai_models" | "matching_rules" | "sensitivity_scoring" | "review_evidence" | "external_sources" | "performance" | "integrations" | "audit_trail" | "expert_settings";

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || !user) return;

    axios.get("/api/settings")
      .then((res) => setSettings(res.data))
      .catch(() => setError("Failed to load settings"));
  }, [authLoading, user]);

  const saveSettings = async () => {
    setSaving(true);
    try {
      await axios.patch("/api/settings", settings);
      setSuccess("Settings saved successfully");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: unknown) {
      const message = axios.isAxiosError(err)
        ? err.response?.data?.detail
        : null;
      setError(message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const updateSetting = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    if (!settings) return;
    setSettings({ ...settings, [key]: value });
  };

  if (authLoading || !settings) {
    return (
      <DashboardLayout requiredRole="admin">
        <div className="px-4 py-8 lg:px-6 flex items-center justify-center h-64">
          <p className="text-slate-500">Loading settings...</p>
        </div>
      </DashboardLayout>
    );
  }

  const tabs: Array<{ id: SettingsTab; label: string }> = [
    { id: "general", label: "General" },
    { id: "detection_engines", label: "Detection engines" },
    { id: "ai_models", label: "AI models" },
    { id: "matching_rules", label: "Matching rules" },
    { id: "sensitivity_scoring", label: "Sensitivity and scoring" },
    { id: "review_evidence", label: "Review and evidence" },
    { id: "external_sources", label: "External sources" },
    { id: "performance", label: "Performance" },
    { id: "integrations", label: "Integrations" },
    { id: "audit_trail", label: "Audit trail" },
    { id: "expert_settings", label: "Expert settings" },
  ];

  const coreEngines = ENGINE_CATALOG.filter((engine) => engine.tier === "core");
  const engineWeightTotal = Object.values(settings.engine_weights).reduce(
    (sum, weight) => sum + Number(weight || 0),
    0,
  );

  return (
    <DashboardLayout requiredRole="admin">
      <div className="px-4 py-6 lg:px-6 lg:py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">System Settings</h1>
          <p className="text-slate-500 mt-2 dark:text-slate-400">
            Configure system behavior, detection engines, and integrations.
          </p>
        </div>

        {error && (
          <div className="mb-6 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-6 flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300">
            <Shield size={16} className="mt-0.5 shrink-0" />
            <span>{success}</span>
          </div>
        )}



        <div className="mb-6 flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${activeTab === tab.id
                ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-[28px] border border-slate-200 p-6 shadow-sm dark:bg-slate-950 dark:border-slate-800">
          {activeTab === "general" && (
            <div className="space-y-6">
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-[0.16em] mb-3 dark:text-slate-400">
                  Detection Thresholds
                </label>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Default Similarity Threshold
                    </label>
                    <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min="0.1"
                        max="0.9"
                        step="0.05"
                        value={settings.default_threshold}
                        onChange={(e) => updateSetting("default_threshold", parseFloat(e.target.value))}
                        className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600 dark:bg-slate-800"
                      />
                      <span className="text-lg font-bold text-blue-600 w-16 text-right dark:text-blue-400">
                        {(settings.default_threshold * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-2 dark:text-slate-400">
                      Pairs scoring above this threshold will be flagged for review.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "detection_engines" && (
            <div className="space-y-6">
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-[0.16em] mb-3 dark:text-slate-400">
                  Engine Weights
                </label>
                <p className="text-xs text-slate-500 mb-4 dark:text-slate-400">
                  Adjust contribution weights for each similarity detection engine. Values should sum to 1.0 (100%).
                </p>

                <div className="mb-6 flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4 dark:border-slate-800 dark:bg-slate-900">
                  <div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">
                      Engine coverage total
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      Current combined weight across all engines
                    </div>
                  </div>
                  <div className={`text-lg font-bold ${Math.abs(engineWeightTotal - 1) < 0.01
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-amber-600 dark:text-amber-400"
                    }`}>
                    {(engineWeightTotal * 100).toFixed(0)}%
                  </div>
                </div>

                <div className="space-y-4">
                  {coreEngines.map((engine) => {
                    const weight = settings.engine_weights[engine.key] || 0;
                    return (
                      <div key={engine.key} className="rounded-2xl border border-slate-200 p-5 dark:border-slate-800">
                        <div className="mb-3 flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-semibold text-slate-900 dark:text-white">
                              {engine.label}
                            </div>
                            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                              {engine.description}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={weight}
                            onChange={(e) => updateSetting("engine_weights", {
                              ...settings.engine_weights,
                              [engine.key]: parseFloat(e.target.value),
                            })}
                            className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600 dark:bg-slate-800"
                          />
                          <span className="w-16 text-right text-sm font-bold text-blue-600 dark:text-blue-400">
                            {(weight * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {activeTab === "integrations" && (
            <div className="space-y-6">
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-[0.16em] mb-3 dark:text-slate-400">
                  OpenAI Configuration
                </label>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">API Key</label>
                    <input
                      type="password"
                      value={settings.openai_api_key}
                      onChange={(e) => updateSetting("openai_api_key", e.target.value)}
                      placeholder={
                        settings.openai_api_key_configured
                          ? "Leave blank to keep current key"
                          : "Enter OpenAI API key"
                      }
                      className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Base URL</label>
                      <input
                        type="text"
                        value={settings.openai_base_url}
                        onChange={(e) => updateSetting("openai_base_url", e.target.value)}
                        placeholder="https://api.openai.com/v1"
                        className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Model</label>
                      <input
                        type="text"
                        value={settings.openai_model}
                        onChange={(e) => updateSetting("openai_model", e.target.value)}
                        placeholder="gpt-3.5-turbo"
                        className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-6 border-t border-slate-200 dark:border-slate-800">
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-[0.16em] mb-3 dark:text-slate-400">
                  Anthropic Configuration
                </label>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">API Key</label>
                    <input
                      type="password"
                      value={settings.anthropic_api_key}
                      onChange={(e) => updateSetting("anthropic_api_key", e.target.value)}
                      placeholder={
                        settings.anthropic_api_key_configured
                          ? "Leave blank to keep current key"
                          : "Enter Anthropic API key"
                      }
                      className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Model</label>
                    <input
                      type="text"
                      value={settings.anthropic_model}
                      onChange={(e) => updateSetting("anthropic_model", e.target.value)}
                      placeholder="claude-3-opus-20240229"
                      className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-6 border-t border-slate-200 dark:border-slate-800">
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-[0.16em] mb-3 dark:text-slate-400">
                  MOSS Integration
                </label>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">User ID</label>
                  <input
                    type="password"
                    value={settings.moss_user_id}
                    onChange={(e) => updateSetting("moss_user_id", e.target.value)}
                    placeholder={
                      settings.moss_user_id_configured
                        ? "Leave blank to keep current MOSS user ID"
                        : "Enter MOSS user ID"
                    }
                    className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === "performance" && (
            <div className="space-y-6">
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-[0.16em] mb-3 dark:text-slate-400">
                  Embedding Configuration
                </label>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Runtime</label>
                    <select
                      value={settings.embedding_runtime}
                      onChange={(e) => updateSetting("embedding_runtime", e.target.value)}
                      className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    >
                      <option value="local_unixcoder">Local UniXcoder (GPU/CPU)</option>
                      <option value="remote_openai_compatible">Remote OpenAI-Compatible Server</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Device</label>
                      <select
                        value={settings.embedding_device}
                        onChange={(e) => updateSetting("embedding_device", e.target.value)}
                        className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                      >
                        <option value="auto">Auto Detect</option>
                        <option value="cuda">CUDA / GPU</option>
                        <option value="cpu">CPU</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Batch Size</label>
                      <input
                        type="number"
                        min="1"
                        max="256"
                        value={settings.embedding_batch_size}
                        onChange={(e) => updateSetting("embedding_batch_size", parseInt(e.target.value))}
                        className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-6 border-t border-slate-200 dark:border-slate-800">
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-[0.16em] mb-3 dark:text-slate-400">
                  Resource Limits
                </label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Maximum File Size (MB)</label>
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={settings.max_file_size_mb}
                      onChange={(e) => updateSetting("max_file_size_mb", parseInt(e.target.value))}
                      className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Maximum Files Per Job</label>
                    <input
                      type="number"
                      min="1"
                      max="10000"
                      value={settings.max_files_per_job}
                      onChange={(e) => updateSetting("max_files_per_job", parseInt(e.target.value))}
                      className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Processing Batch Size</label>
                    <input
                      type="number"
                      min="1"
                      max="1024"
                      value={settings.batch_size}
                      onChange={(e) => updateSetting("batch_size", parseInt(e.target.value))}
                      className="h-12 w-full mt-1 px-4 border border-slate-200 rounded-2xl bg-white dark:bg-slate-900 dark:border-slate-800 text-slate-900 dark:text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "expert_settings" && (
            <div className="space-y-6">
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-[0.16em] mb-3 dark:text-slate-400">
                  Advanced Settings
                </label>
                <p className="text-xs text-slate-500 mb-4 dark:text-slate-400">
                  These settings are for advanced configuration only. Modify only if you understand the implications.
                </p>
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/20 dark:bg-amber-500/10">
                  <p className="text-sm text-amber-700 dark:text-amber-300">
                    ⚠️ Changing these values may affect detection accuracy and system performance.
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="mt-8 pt-6 border-t border-slate-200 dark:border-slate-800">
            <div className="flex justify-end">
              <button
                onClick={saveSettings}
                disabled={saving}
                className="px-6 py-3 bg-blue-600 text-white rounded-2xl font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors dark:bg-blue-500 dark:hover:bg-blue-600"
              >
                {saving ? "Saving..." : "Save Settings"}
              </button>
            </div>
          </div>
        </div>


      </div>
    </DashboardLayout>
  );
}
