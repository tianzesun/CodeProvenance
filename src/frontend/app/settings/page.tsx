"use client";

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { Settings, Cpu, Zap, Shield, Database, RefreshCw, Save, AlertTriangle, CheckCircle } from 'lucide-react';

const ENGINE_CATALOG = [
  {
    key: "token",
    label: "Token",
    tier: "core",
    description: "Token-level overlap and lexical similarity.",
  },
  {
    key: "ast",
    label: "AST",
    tier: "core",
    description: "Structural similarity across parsed syntax trees.",
  },
  {
    key: "winnowing",
    label: "Winnowing",
    tier: "core",
    description: "K-gram fingerprinting for copy-paste style matches.",
  },
  {
    key: "gst",
    label: "GST",
    tier: "core",
    description: "Greedy String Tiling for long contiguous match blocks.",
  },
  {
    key: "semantic",
    label: "Semantic",
    tier: "core",
    description: "Meaning-level similarity via embedding or model-backed analysis.",
  },
  {
    key: "web",
    label: "Web",
    tier: "core",
    description: "External-source similarity checks against web-accessible code.",
  },
  {
    key: "ai_detection",
    label: "AI Detection",
    tier: "optional",
    description: "Authorship-style and AI-generated code detection signals.",
  },
  {
    key: "execution_cfg",
    label: "Execution/CFG",
    tier: "optional",
    description: "Behavioral/runtime checks and control-flow graph evidence.",
  },
];

const DEFAULT_ENGINE_WEIGHTS = {
  token: 0.18,
  ast: 0.22,
  winnowing: 0.16,
  gst: 0.16,
  semantic: 0.18,
  web: 0.10,
  ai_detection: 0,
  execution_cfg: 0,
};

const LEGACY_ENGINE_KEY_MAP = {
  fingerprint: "token",
  embedding: "semantic",
  unixcoder: "semantic",
  ngram: "gst",
  structural: "gst",
  graph: "execution_cfg",
  execution: "execution_cfg",
};

function normalizeEngineWeights(weights?: Record<string, number>) {
  const normalized = Object.fromEntries(
    Object.keys(DEFAULT_ENGINE_WEIGHTS).map((key) => [key, 0]),
  ) as Record<string, number>;
  const seenKeys = new Set<string>();

  if (!weights || typeof weights !== "object") {
    return { ...DEFAULT_ENGINE_WEIGHTS };
  }

  Object.entries(weights).forEach(([rawKey, rawValue]) => {
    const targetKey = LEGACY_ENGINE_KEY_MAP[rawKey as keyof typeof LEGACY_ENGINE_KEY_MAP] || rawKey;
    if (!(targetKey in normalized)) {
      return;
    }

    const value = Number(rawValue);
    if (!Number.isFinite(value)) {
      return;
    }

    normalized[targetKey] += value;
    seenKeys.add(targetKey);
  });

  if (!seenKeys.size) {
    return { ...DEFAULT_ENGINE_WEIGHTS };
  }

  Object.entries(DEFAULT_ENGINE_WEIGHTS).forEach(([key, value]) => {
    if (!seenKeys.has(key)) {
      normalized[key] = value;
    }
  });

  return normalized;
}

function areWeightsEqual(a?: Record<string, number>, b?: Record<string, number>) {
  const left = normalizeEngineWeights(a);
  const right = normalizeEngineWeights(b);

  return ENGINE_CATALOG.every(
    ({ key }) => Math.abs((left[key] || 0) - (right[key] || 0)) < 0.01,
  );
}

interface EngineConfig {
  weights: Record<string, number>;
  baselines: Record<string, number>;
  arbitration: Record<string, any>;
  ast_boost: Record<string, any>;
  decision: Record<string, any>;
  thresholds: Record<string, any>;
  toggles: Record<string, boolean>;
  performance: Record<string, any>;
  advanced: Record<string, any>;
}

interface Settings {
  default_threshold: number;
  openai_api_key: string;
  openai_api_key_configured: boolean;
  openai_base_url: string;
  openai_model: string;
  anthropic_api_key: string;
  anthropic_api_key_configured: boolean;
  anthropic_model: string;
  ai_detection_enabled: boolean;
  gptzero_api_key: string;
  gptzero_api_key_configured: boolean;
  grammarly_api_key: string;
  grammarly_api_key_configured: boolean;
  web_analysis_enabled: boolean;
  github_api_token: string;
  github_api_token_configured: boolean;
  stackexchange_api_key: string;
  stackexchange_api_key_configured: boolean;
  execution_cfg_enabled: boolean;
  embedding_runtime: string;
  embedding_model: string;
  embedding_server_url: string | null;
  embedding_server_host: string | null;
  embedding_server_port: number;
  embedding_device: string;
  embedding_batch_size: number;
  engine_weights: { [key: string]: number };
  baseline_correction: { baselines: { [key: string]: number } };
  batch_size: number;
  max_file_size_mb: number;
  max_files_per_job: number;
}

type SettingsTab = "general" | "llm" | "engines" | "engine-config" | "calibration" | "advanced";

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [engineConfig, setEngineConfig] = useState<EngineConfig | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [calibrating, setCalibrating] = useState(false);
  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const enginePresets = [
    {
      name: "Balanced (Recommended)",
      description: "Good all-around performance for most use cases",
      weights: {
        token: 0.18,
        ast: 0.22,
        winnowing: 0.16,
        gst: 0.16,
        semantic: 0.18,
        web: 0.10,
        ai_detection: 0,
        execution_cfg: 0,
      },
    },
    {
      name: "Copy-Paste Detection",
      description:
        "Best for detecting direct copying, reformatting, minor changes",
      weights: {
        token: 0.28,
        ast: 0.18,
        winnowing: 0.22,
        gst: 0.20,
        semantic: 0.07,
        web: 0.05,
        ai_detection: 0,
        execution_cfg: 0,
      },
    },
    {
      name: "Semantic Similarity",
      description: "Detect logic similarity even with heavy obfuscation",
      weights: {
        token: 0.10,
        ast: 0.17,
        winnowing: 0.08,
        gst: 0.10,
        semantic: 0.35,
        web: 0.10,
        ai_detection: 0.05,
        execution_cfg: 0.05,
      },
    },
    {
      name: "Structure Focused",
      description: "Prioritize control flow and program structure patterns",
      weights: {
        token: 0.12,
        ast: 0.30,
        winnowing: 0.08,
        gst: 0.15,
        semantic: 0.10,
        web: 0.05,
        ai_detection: 0.05,
        execution_cfg: 0.15,
      },
    },
    {
      name: "Strict Comparison",
      description: "High sensitivity - highest false positive rate",
      weights: {
        token: 0.22,
        ast: 0.22,
        winnowing: 0.18,
        gst: 0.18,
        semantic: 0.10,
        web: 0.05,
        ai_detection: 0.02,
        execution_cfg: 0.03,
      },
    },
  ];

  useEffect(() => {
    if (authLoading || !user || user.role !== "admin") {
      return;
    }
    // Load legacy settings
    axios
      .get("/api/settings")
      .then((res) =>
        setSettings({
          baseline_correction: {
            baselines: {
              winnowing: 0.25,
              ast: 0.25,
              token: 0.15,
              semantic: 0.70,
            }
          },
          ...res.data,
          engine_weights: normalizeEngineWeights(res.data?.engine_weights),
        }),
      )
      .catch(() => { });

    // Load new engine configuration
    axios
      .get("/api/settings/engine-config")
      .then((res) => setEngineConfig(res.data))
      .catch((err) => console.error("Failed to load engine config:", err));
  }, [authLoading, user]);

  const handleSave = () => {
    if (!settings) return;
    setSaving(true);
    setError(null);
    setSuccess(null);

    axios.patch("/api/settings", settings).then(() => {
      setSettings((current) => {
        if (!current) return current;
        return {
          ...current,
          engine_weights: normalizeEngineWeights(current.engine_weights),
          openai_api_key: "",
          anthropic_api_key: "",
          gptzero_api_key: "",
          grammarly_api_key: "",
          github_api_token: "",
          stackexchange_api_key: "",
          openai_api_key_configured:
            current.openai_api_key_configured || current.openai_api_key.trim().length > 0,
          anthropic_api_key_configured:
            current.anthropic_api_key_configured || current.anthropic_api_key.trim().length > 0,
          gptzero_api_key_configured:
            current.gptzero_api_key_configured || current.gptzero_api_key.trim().length > 0,
          grammarly_api_key_configured:
            current.grammarly_api_key_configured || current.grammarly_api_key.trim().length > 0,
          github_api_token_configured:
            current.github_api_token_configured || current.github_api_token.trim().length > 0,
          stackexchange_api_key_configured:
            current.stackexchange_api_key_configured ||
            current.stackexchange_api_key.trim().length > 0,
        };
      });
      setSuccess("Settings saved successfully");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }).catch((err) => {
      setError(err.response?.data?.detail || "Failed to save settings");
    }).finally(() => {
      setSaving(false);
    });
  };

  const handleSaveEngineConfig = async () => {
    if (!engineConfig) return;
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await axios.put('/api/settings/engine-config', engineConfig);
      setSuccess(response.data.message || "Engine configuration saved successfully");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to save engine configuration");
    } finally {
      setSaving(false);
    }
  };

  const handleCalibration = async () => {
    setCalibrating(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await axios.post('/api/settings/calibrate');
      setSuccess(response.data.message || "Calibration completed successfully");

      // Reload engine config after calibration
      const configResponse = await axios.get('/api/settings/engine-config');
      setEngineConfig(configResponse.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Calibration failed");
    } finally {
      setCalibrating(false);
    }
  };

  const updateSetting = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    if (!settings) return;
    setSettings({ ...settings, [key]: value });
  };

  const updateEngineWeight = (engine: string, value: number) => {
    if (!settings) return;
    setSettings({
      ...settings,
      engine_weights: normalizeEngineWeights({
        ...settings.engine_weights,
        [engine]: value,
      }),
    });
  };

  if (!settings) {
    return (
      <DashboardLayout requiredRole="admin">
        <div className="p-6 flex items-center justify-center h-64">
          <p className="text-slate-500">Loading settings...</p>
        </div>
      </DashboardLayout>
    );
  }

  const tabs: Array<{ id: SettingsTab; label: string; adminOnly?: boolean }> = [
    { id: "general", label: "General" },
    { id: "llm", label: "AI & Keys" },
    { id: "engines", label: "Engine Setup" },
    { id: "engine-config", label: "Scoring Rules", adminOnly: true },
    { id: "calibration", label: "Accuracy Tuning", adminOnly: true },
    { id: "advanced", label: "Limits" },
  ];
  const engineWeights = normalizeEngineWeights(settings.engine_weights);
  const coreEngines = ENGINE_CATALOG.filter((engine) => engine.tier === "core");
  const optionalEngines = ENGINE_CATALOG.filter((engine) => engine.tier === "optional");
  const engineWeightTotal = Object.values(engineWeights).reduce(
    (sum, weight) => sum + Number(weight || 0),
    0,
  );

  return (
    <DashboardLayout requiredRole="admin">
      <div className="p-4 lg:p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
          <p className="text-slate-500 mt-1">
            Configure system behavior and integrations.
          </p>
        </div>

        <div className="flex gap-2 mb-6 border-b border-slate-200">
          {tabs.filter(tab => !tab.adminOnly || user?.role === "admin").map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-6">
          {activeTab === "general" && (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  Default Similarity Threshold
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="0.1"
                    max="0.9"
                    step="0.05"
                    value={settings.default_threshold}
                    onChange={(e) =>
                      updateSetting(
                        "default_threshold",
                        parseFloat(e.target.value),
                      )
                    }
                    className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                  <span className="text-lg font-bold text-blue-600 w-16 text-right">
                    {(settings.default_threshold * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  Pairs scoring above this threshold will be flagged for review.
                </p>
              </div>
            </>
          )}

          {activeTab === "llm" && (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  OpenAI Configuration
                </label>
                <div className="space-y-3">
                  <div>
                    <label className="text-sm text-slate-600">API Key</label>
                    <input
                      type="password"
                      value={settings.openai_api_key}
                      onChange={(e) =>
                        updateSetting("openai_api_key", e.target.value)
                      }
                      placeholder={
                        settings.openai_api_key_configured
                          ? "Leave blank to keep current OpenAI key"
                          : "Enter OpenAI API key"
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                    <p className="text-xs text-slate-400 mt-2">
                      Saved as a workspace setting. The current key is never returned to the browser.
                    </p>
                  </div>
                  <div>
                    <label className="text-sm text-slate-600">Base URL</label>
                    <input
                      type="text"
                      value={settings.openai_base_url}
                      onChange={(e) =>
                        updateSetting("openai_base_url", e.target.value)
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-slate-600">Model</label>
                    <input
                      type="text"
                      value={settings.openai_model}
                      onChange={(e) =>
                        updateSetting("openai_model", e.target.value)
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100">
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  Anthropic Configuration
                </label>
                <div className="space-y-3 mt-3">
                  <div>
                    <label className="text-sm text-slate-600">API Key</label>
                    <input
                      type="password"
                      value={settings.anthropic_api_key}
                      onChange={(e) =>
                        updateSetting("anthropic_api_key", e.target.value)
                      }
                      placeholder={
                        settings.anthropic_api_key_configured
                          ? "Leave blank to keep current Anthropic key"
                          : "Enter Anthropic API key"
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                    <p className="text-xs text-slate-400 mt-2">
                      Saved as a workspace setting. The current key is never returned to the browser.
                    </p>
                  </div>
                  <div>
                    <label className="text-sm text-slate-600">Model</label>
                    <input
                      type="text"
                      value={settings.anthropic_model}
                      onChange={(e) =>
                        updateSetting("anthropic_model", e.target.value)
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100">
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  Optional Analysis Engines
                </label>
                <div className="space-y-4 mt-3">
                  {[
                    {
                      key: "web_analysis_enabled" as const,
                      label: "Web",
                      description: "Search public code and Q&A sources during assignment checks.",
                    },
                    {
                      key: "ai_detection_enabled" as const,
                      label: "AI Detection",
                      description: "Add per-file authorship and AI-generation signals to reports.",
                    },
                    {
                      key: "execution_cfg_enabled" as const,
                      label: "Execution/CFG",
                      description: "Allow behavioral and control-flow checks when this engine is selected.",
                    },
                  ].map((item) => (
                    <div key={item.key} className="flex items-center gap-4 rounded-xl border border-slate-200 p-4">
                      <div className="flex-1">
                        <div className="text-sm font-medium text-slate-900">{item.label}</div>
                        <div className="text-xs text-slate-500 mt-1">{item.description}</div>
                      </div>
                      <button
                        type="button"
                        onClick={() => updateSetting(item.key, !settings[item.key])}
                        className={`w-12 h-6 rounded-full transition-colors ${settings[item.key] ? 'bg-blue-600' : 'bg-slate-300'}`}
                      >
                        <div className={`w-5 h-5 rounded-full bg-white shadow transform transition-transform ${settings[item.key] ? 'translate-x-6' : 'translate-x-0.5'}`} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100">
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  Web Provider Keys
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  <div>
                    <label className="text-sm text-slate-600">GitHub Token</label>
                    <input
                      type="password"
                      value={settings.github_api_token}
                      onChange={(e) =>
                        updateSetting("github_api_token", e.target.value)
                      }
                      placeholder={
                        settings.github_api_token_configured
                          ? "Leave blank to keep current GitHub token"
                          : "Enter GitHub token"
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                    <p className="text-xs text-slate-400 mt-2">
                      Used by the Web engine for GitHub source checks.
                    </p>
                  </div>
                  <div>
                    <label className="text-sm text-slate-600">Stack Exchange Key</label>
                    <input
                      type="password"
                      value={settings.stackexchange_api_key}
                      onChange={(e) =>
                        updateSetting("stackexchange_api_key", e.target.value)
                      }
                      placeholder={
                        settings.stackexchange_api_key_configured
                          ? "Leave blank to keep current Stack Exchange key"
                          : "Enter Stack Exchange key"
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                    <p className="text-xs text-slate-400 mt-2">
                      Used by the Web engine for Stack Overflow and Stack Exchange checks.
                    </p>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100">
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  AI Detection Provider Keys
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  <div>
                    <label className="text-sm text-slate-600">GPTZero API Key</label>
                    <input
                      type="password"
                      value={settings.gptzero_api_key}
                      onChange={(e) =>
                        updateSetting("gptzero_api_key", e.target.value)
                      }
                      placeholder={
                        settings.gptzero_api_key_configured
                          ? "Leave blank to keep current GPTZero key"
                          : "Enter GPTZero API key"
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                    <p className="text-xs text-slate-400 mt-2">
                      Stored for AI Detection provider integrations.
                    </p>
                  </div>
                  <div>
                    <label className="text-sm text-slate-600">Grammarly API Key</label>
                    <input
                      type="password"
                      value={settings.grammarly_api_key}
                      onChange={(e) =>
                        updateSetting("grammarly_api_key", e.target.value)
                      }
                      placeholder={
                        settings.grammarly_api_key_configured
                          ? "Leave blank to keep current Grammarly key"
                          : "Enter Grammarly API key"
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                    <p className="text-xs text-slate-400 mt-2">
                      Stored for AI Detection provider integrations.
                    </p>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100">
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  Embedding Configuration
                </label>
                <div className="space-y-3 mt-3">
                  <div>
                    <label className="text-sm text-slate-600">
                      Embedding Runtime
                    </label>
                    <select
                      value={settings.embedding_runtime}
                      onChange={(e) =>
                        updateSetting("embedding_runtime", e.target.value)
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white"
                    >
                      <option value="local_unixcoder">Local UniXcoder (GPU/CPU)</option>
                      <option value="remote_openai_compatible">Remote OpenAI-Compatible Server</option>
                    </select>
                    <p className="text-xs text-slate-400 mt-2">
                      Use local UniXcoder for on-box GPU/CPU inference, or point to an OpenAI-compatible embedding server such as vLLM serving Qwen embedding models.
                    </p>
                  </div>
                  <div>
                    <label className="text-sm text-slate-600">
                      Embedding Model Name
                    </label>
                    <input
                      type="text"
                      value={settings.embedding_model}
                      onChange={(e) =>
                        updateSetting("embedding_model", e.target.value)
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="text-sm text-slate-600">
                        Embedding Server IP / Host
                      </label>
                      <input
                        type="text"
                        value={settings.embedding_server_host || ""}
                        placeholder="192.168.1.50 or gpu-server.local"
                        onChange={(e) =>
                          updateSetting(
                            "embedding_server_host",
                            e.target.value || null,
                          )
                        }
                        className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-sm text-slate-600">
                        Embedding Server Port
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="65535"
                        value={settings.embedding_server_port}
                        onChange={(e) =>
                          updateSetting(
                            "embedding_server_port",
                            parseInt(e.target.value || "8000", 10),
                          )
                        }
                        className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-sm text-slate-600">
                      Full Embedding Server URL Override
                    </label>
                    <input
                      type="text"
                      value={settings.embedding_server_url || ""}
                      placeholder="http://localhost:8000/v1"
                      onChange={(e) =>
                        updateSetting(
                          "embedding_server_url",
                          e.target.value || null,
                        )
                      }
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    />
                    <p className="text-xs text-slate-400 mt-2">
                      Optional. If left blank, IntegrityDesk will build the endpoint from the server IP/host and port above. Use this override for custom paths like `/v1`.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="text-sm text-slate-600">
                        Local Device
                      </label>
                      <select
                        value={settings.embedding_device}
                        onChange={(e) =>
                          updateSetting("embedding_device", e.target.value)
                        }
                        className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white"
                      >
                        <option value="auto">Auto Detect</option>
                        <option value="cuda">CUDA / GPU</option>
                        <option value="cpu">CPU</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-sm text-slate-600">
                        Embedding Batch Size
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="256"
                        value={settings.embedding_batch_size}
                        onChange={(e) =>
                          updateSetting("embedding_batch_size", parseInt(e.target.value))
                        }
                        className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      />
                    </div>
                  </div>

                  <div className="mt-6">
                    <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">
                      Decision Thresholds
                    </label>

                    <div className="rounded-xl border border-slate-200 p-4 space-y-4">
                      {[
                        { key: "default_threshold", label: "Default Detection Threshold", min: 0.1, max: 0.9, step: 0.05, value: settings.default_threshold, description: "Pairs above this score will be flagged" },
                        { key: "minimum_confidence", label: "Minimum Confidence", min: 0.0, max: 1.0, step: 0.05, value: 0.4, description: "Minimum confidence required to flag results" },
                        { key: "minimum_engine_agreement", label: "Required Engine Agreement", min: 1, max: 8, step: 1, value: 2, description: "Minimum number of engines that must agree" },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center gap-4">
                          <div className="flex-1">
                            <div className="text-sm font-medium text-slate-900">{item.label}</div>
                            <div className="text-xs text-slate-500 mt-1">{item.description}</div>
                          </div>
                          <input
                            type="range"
                            min={item.min}
                            max={item.max}
                            step={item.step}
                            value={item.value}
                            className="w-48 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                          />
                          <span className="w-16 text-right text-sm font-bold text-blue-600">
                            {item.value < 10 ? `${(item.value * 100).toFixed(0)}%` : item.value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-6">
                    <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">
                      Feature Toggles
                    </label>

                    <div className="rounded-xl border border-slate-200 p-4 space-y-4">
                      {[
                        { key: "baseline_correction", label: "Baseline Noise Correction", enabled: true, description: "Subtract language noise floor from all scores" },
                        { key: "bayesian_arbitration", label: "Bayesian Score Fusion", enabled: true, description: "Statistical arbitration between engine scores" },
                        { key: "ast_boost", label: "AST High Score Boost", enabled: true, description: "Guarantee minimum score for high AST similarity" },
                        { key: "result_caching", label: "Result Caching", enabled: true, description: "Cache similarity calculation results" },
                      ].map((item) => (
                        <div key={item.key} className="flex items-center gap-4">
                          <div className="flex-1">
                            <div className="text-sm font-medium text-slate-900">{item.label}</div>
                            <div className="text-xs text-slate-500 mt-1">{item.description}</div>
                          </div>
                          <button
                            className={`w-12 h-6 rounded-full transition-colors ${item.enabled ? 'bg-blue-600' : 'bg-slate-300'}`}
                          >
                            <div className={`w-5 h-5 rounded-full bg-white shadow transform transition-transform ${item.enabled ? 'translate-x-6' : 'translate-x-0.5'}`} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-6">
                    <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">
                      Performance Tuning
                    </label>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {[
                        { key: "parallel_engine_execution", label: "Parallel Engine Execution", value: 4 },
                        { key: "result_cache_ttl", label: "Cache TTL (seconds)", value: 3600 },
                        { key: "engine_timeout_ms", label: "Engine Timeout (ms)", value: 15000 },
                        { key: "maximum_batch_size", label: "Maximum Batch Size", value: 256 },
                      ].map((item) => (
                        <div key={item.key} className="rounded-xl border border-slate-200 p-4">
                          <label className="block text-sm font-medium text-slate-700 mb-2">{item.label}</label>
                          <input
                            type="number"
                            value={item.value}
                            className="w-full px-3 py-2 border border-slate-200 rounded-lg"
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                </div>
              </div>
            </>
          )}

          {activeTab === "engines" && (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">
                  Recommended Setups
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
                  {enginePresets.map((preset, idx) => (
                    <button
                      key={idx}
                      onClick={() =>
                        setSettings({
                          ...settings!,
                          engine_weights: normalizeEngineWeights(preset.weights),
                        })
                      }
                      className={`p-4 border rounded-xl text-left transition-all hover:border-blue-400 hover:bg-blue-50 ${areWeightsEqual(engineWeights, preset.weights)
                          ? "border-blue-500 bg-blue-50 ring-2 ring-blue-200"
                          : "border-slate-200"
                        }`}
                    >
                      <div className="font-semibold text-slate-900">
                        {preset.name}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {preset.description}
                      </div>
                    </button>
                  ))}
                </div>

                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">
                  Engines Used for Checks
                </label>
                <p className="text-xs text-slate-400 mb-4">
                  Turn engines on or off and choose how much each one should
                  influence normal assignment checks.
                </p>
                <div className="mb-4 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">
                      Engine coverage total
                    </div>
                    <div className="text-xs text-slate-500">
                      Current combined weight across all engines
                    </div>
                  </div>
                  <div className={`text-lg font-bold ${Math.abs(engineWeightTotal - 1) < 0.01
                      ? "text-emerald-600"
                      : "text-amber-600"
                    }`}>
                    {(engineWeightTotal * 100).toFixed(0)}%
                  </div>
                </div>

                <div className="space-y-6">
                  {[
                    { title: "Core Engines (6)", engines: coreEngines },
                    { title: "Optional Engines (2)", engines: optionalEngines },
                  ].map((section) => (
                    <div key={section.title}>
                      <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-600">
                        {section.title}
                      </div>
                      <div className="space-y-4">
                        {section.engines.map((engine) => {
                          const weight = engineWeights[engine.key] || 0;

                           return (
                             <div key={engine.key} className={`rounded-xl border ${weight < 0.01 ? 'border-slate-200 opacity-60' : 'border-slate-200'} p-4`}>
                               <div className="mb-3 flex items-start justify-between gap-3">
                                 <div>
                                   <div className="text-sm font-semibold text-slate-900">
                                     {engine.label}
                                   </div>
                                   <div className="mt-1 text-xs text-slate-500">
                                     {engine.description}
                                   </div>
                                 </div>
                                 <div className="flex items-center gap-3">
                                   <button
                                     onClick={() => updateEngineWeight(engine.key, weight > 0.01 ? 0 : engine.tier === "core" ? 0.15 : 0.05)}
                                     className={`w-10 h-5 rounded-full transition-colors ${weight > 0.01 ? 'bg-emerald-500' : 'bg-slate-300'}`}
                                   >
                                     <div className={`w-4 h-4 rounded-full bg-white shadow transform transition-transform ${weight > 0.01 ? 'translate-x-5' : 'translate-x-0.5'}`} />
                                   </button>
                                   <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${engine.tier === "core"
                                       ? "bg-blue-50 text-blue-700"
                                       : "bg-slate-100 text-slate-600"
                                     }`}>
                                     {engine.tier}
                                   </span>
                                 </div>
                               </div>

                               <div className="flex items-center gap-3">
                                 <input
                                   type="range"
                                   min="0"
                                   max="1"
                                   step="0.05"
                                   value={weight}
                                   onChange={(e) =>
                                     updateEngineWeight(
                                       engine.key,
                                       parseFloat(e.target.value),
                                     )
                                   }
                                   className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                                 />
                                 <span className="w-14 text-right text-sm font-medium text-blue-600">
                                   {(weight * 100).toFixed(0)}%
                                 </span>
                               </div>
                             </div>
                           );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {activeTab === "engine-config" && (
            <>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">Scoring Rules</h3>
                  <p className="text-sm text-slate-600 mt-1">
                    Fine-tune score weights, noise correction, thresholds, and performance behavior.
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleCalibration}
                    disabled={calibrating}
                    className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors flex items-center gap-2 disabled:opacity-50"
                  >
                    {calibrating ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4" />
                    )}
                    Auto-Calibrate
                  </button>
                  <button
                    onClick={handleSaveEngineConfig}
                    disabled={saving}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50"
                  >
                    {saving ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    Save Rules
                  </button>
                </div>
              </div>

              {error && (
                <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-600" />
                    <span className="font-semibold text-red-900">Error</span>
                  </div>
                  <p className="text-sm text-red-700 mt-1">{error}</p>
                </div>
              )}

              {success && (
                <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-xl">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                    <span className="font-semibold text-green-900">Success</span>
                  </div>
                  <p className="text-sm text-green-700 mt-1">{success}</p>
                </div>
              )}

              {!engineConfig ? (
                <div className="flex items-center justify-center h-64">
                  <RefreshCw className="h-8 w-8 animate-spin text-slate-400" />
                  <span className="ml-2 text-slate-600">Loading engine configuration...</span>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="rounded-xl border border-slate-200 p-6">
                    <h4 className="text-md font-semibold text-slate-900 mb-4">Score Weights</h4>
                    <p className="text-sm text-slate-600 mb-4">
                      Control how much each scoring signal contributes to the final result.
                    </p>

                    <div className="space-y-4">
                      {Object.entries(engineConfig.weights).map(([engine, weight]) => (
                        <div key={engine} className="space-y-2">
                          <div className="flex justify-between items-center">
                            <label className="font-medium capitalize text-slate-700">{engine}</label>
                            <span className="text-sm font-bold text-blue-600">
                              {(weight * 100).toFixed(1)}%
                            </span>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.01"
                            value={weight}
                            onChange={(e) => {
                              const newConfig = { ...engineConfig };
                              newConfig.weights[engine] = parseFloat(e.target.value);
                              setEngineConfig(newConfig);
                            }}
                            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                          />
                        </div>
                      ))}

                      <div className="pt-4 border-t border-slate-100">
                        <div className="flex justify-between items-center">
                          <span className="font-medium text-slate-700">Total</span>
                          <span className={`font-bold ${Math.abs(Object.values(engineConfig.weights).reduce((a, b) => a + b, 0) - 1) < 0.001 ? 'text-green-600' : 'text-red-600'}`}>
                            {(Object.values(engineConfig.weights).reduce((a, b) => a + b, 0) * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 p-6">
                    <h4 className="text-md font-semibold text-slate-900 mb-4">Noise Correction</h4>
                    <p className="text-sm text-slate-600 mb-4">
                      Expected scores for unrelated files in the same language.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.entries(engineConfig.baselines).map(([engine, baseline]) => (
                        <div key={engine} className="space-y-2">
                          <div className="flex justify-between items-center">
                            <label className="font-medium capitalize text-slate-700">{engine}</label>
                            <span className="text-sm font-bold text-blue-600">
                              {(baseline * 100).toFixed(1)}%
                            </span>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.01"
                            value={baseline}
                            onChange={(e) => {
                              const newConfig = { ...engineConfig };
                              newConfig.baselines[engine] = parseFloat(e.target.value);
                              setEngineConfig(newConfig);
                            }}
                            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 p-6">
                    <h4 className="text-md font-semibold text-slate-900 mb-4">Review Thresholds</h4>
                    <p className="text-sm text-slate-600 mb-4">
                      Decide when results should be treated as low, medium, high, or critical.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {Object.entries(engineConfig.thresholds).map(([key, value]) => (
                        <div key={key} className="space-y-2">
                          <label className="block text-sm font-medium text-slate-700 capitalize">
                            {key.replace('_', ' ')}
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            max="1"
                            value={value}
                            onChange={(e) => {
                              const newConfig = { ...engineConfig };
                              newConfig.thresholds[key] = parseFloat(e.target.value);
                              setEngineConfig(newConfig);
                            }}
                            className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 p-6">
                    <h4 className="text-md font-semibold text-slate-900 mb-4">Scoring Options</h4>
                    <p className="text-sm text-slate-600 mb-4">
                      Enable or disable score calculation behaviors.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.entries(engineConfig.toggles).map(([feature, enabled]) => (
                        <div key={feature} className="flex items-center justify-between p-3 border border-slate-200 rounded-lg">
                          <div>
                            <label className="font-medium text-slate-700 capitalize">
                              {feature.replace('_', ' ')}
                            </label>
                            <p className="text-xs text-slate-500 mt-1">
                              {feature === 'baseline_correction' && 'Subtract language noise floor from all scores'}
                              {feature === 'bayesian_arbitration' && 'Statistical arbitration between engine scores'}
                              {feature === 'ast_boost' && 'Guarantee minimum score for high AST similarity'}
                              {feature === 'execution_similarity' && 'Enable execution-based similarity detection'}
                              {feature === 'result_caching' && 'Cache similarity calculation results'}
                            </p>
                          </div>
                          <button
                            onClick={() => {
                              const newConfig = { ...engineConfig };
                              newConfig.toggles[feature] = !enabled;
                              setEngineConfig(newConfig);
                            }}
                            className={`w-12 h-6 rounded-full transition-colors ${enabled ? 'bg-blue-600' : 'bg-slate-300'}`}
                          >
                            <div className={`w-5 h-5 rounded-full bg-white shadow transform transition-transform ${enabled ? 'translate-x-6' : 'translate-x-0.5'}`} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-xl border border-slate-200 p-6">
                    <h4 className="text-md font-semibold text-slate-900 mb-4">Processing Behavior</h4>
                    <p className="text-sm text-slate-600 mb-4">
                      Control concurrency, timeouts, cache duration, and batch size.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      {[
                        { key: 'parallel_engine_execution', label: 'Parallel Engines', type: 'number', min: 1, max: 16 },
                        { key: 'result_cache_ttl', label: 'Cache TTL (sec)', type: 'number', min: 60, max: 36000 },
                        { key: 'engine_timeout_ms', label: 'Timeout (ms)', type: 'number', min: 1000, max: 60000 },
                        { key: 'maximum_batch_size', label: 'Batch Size', type: 'number', min: 1, max: 1024 },
                      ].map((item) => (
                        <div key={item.key} className="space-y-2">
                          <label className="block text-sm font-medium text-slate-700">{item.label}</label>
                          <input
                            type={item.type}
                            min={item.min}
                            max={item.max}
                            value={engineConfig.performance[item.key]}
                            onChange={(e) => {
                              const newConfig = { ...engineConfig };
                              newConfig.performance[item.key] = item.type === 'number' ? parseInt(e.target.value) : e.target.value;
                              setEngineConfig(newConfig);
                            }}
                            className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {activeTab === "calibration" && (
            <>
              <div>
                <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-xl">
                  <div className="font-semibold text-amber-900">Accuracy Tuning</div>
                  <p className="text-xs text-amber-700 mt-1">
                    Changes here are system wide and affect how the platform separates normal similarity from suspicious similarity.
                  </p>
                </div>
                
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">
                  Normal Similarity Baselines
                </label>
                
                <div className="space-y-4">
                  <div className="rounded-xl border border-slate-200 p-4">
                    <div className="mb-3 flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">
                          Normal Similarity Floor
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          Scores below these values are treated as normal language overlap.
                        </div>
                      </div>
                    </div>

                    <div className="mb-4 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">
                          Baseline total
                        </div>
                        <div className="text-xs text-slate-500">
                          Combined normal-similarity allowance
                        </div>
                      </div>
                      <div className={`text-lg font-bold ${Math.abs(Object.values(settings.baseline_correction?.baselines || {}).reduce((a, b) => a + (b as number), 0) - 1) < 0.01
                          ? "text-emerald-600"
                          : "text-amber-600"
                        }`}>
                        {(Object.values(settings.baseline_correction?.baselines || {}).reduce((a, b) => a + (b as number), 0) * 100).toFixed(0)}%
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      {[
                        { key: "winnowing", label: "Winnowing" },
                        { key: "ast", label: "AST" },
                        { key: "token", label: "Token" },
                        { key: "semantic", label: "Semantic" },
                      ].map((item) => {
                        const value = settings.baseline_correction?.baselines?.[item.key] || 0
                        
                        // Auto normalize baselines to always sum exactly 1.0
                        const handleBaselineChange = (key: string, newValue: number) => {
                          const current = { ...settings.baseline_correction.baselines }
                          const othersSum = Object.entries(current)
                            .filter(([k]) => k !== key)
                            .reduce((a, [, v]) => a + (v as number), 0)
                          
                          if (othersSum === 0) {
                            // All other values are zero, distribute remaining equally
                            const count = Object.keys(current).length - 1
                            const equalShare = count > 0 ? (1 - newValue) / count : 0
                            Object.keys(current).forEach(k => {
                              if (k !== key) current[k] = equalShare
                            })
                          } else {
                            // Scale all other values proportionally to maintain total 1.0
                            const scaleFactor = (1 - newValue) / othersSum
                            Object.keys(current).forEach(k => {
                              if (k !== key) current[k] = Math.max(0, Math.min(1, (current[k] as number) * scaleFactor))
                            })
                          }
                          
                          current[key] = newValue
                          
                          setSettings({
                            ...settings,
                            baseline_correction: {
                              ...settings.baseline_correction,
                              baselines: current
                            }
                          })
                        }
                        
                        return (
                        <div key={item.key} className="flex items-center gap-3">
                          <span className="text-sm text-slate-600 w-24">{item.label}</span>
                          <input
                            type="range"
                            min="0"
                            max="1.0"
                            step="0.05"
                            value={value}
                            onChange={(e) => handleBaselineChange(item.key, parseFloat(e.target.value))}
                            className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                          />
                          <span className="w-10 text-right text-sm font-medium text-blue-600">
                            {(value * 100).toFixed(0)}%
                          </span>
                        </div>
                      )})}
                    </div>
                  </div>
                </div>
                
                <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                  <button className="px-4 py-3 bg-slate-100 text-slate-700 font-medium rounded-lg hover:bg-slate-200 transition-colors">
                    Test Against Benchmark
                  </button>
                  <button className="px-4 py-3 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 transition-colors">
                    Tune Automatically
                  </button>
                </div>
              </div>
            </>
          )}

          {activeTab === "advanced" && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Batch Size Per Run
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="256"
                    value={settings.batch_size}
                    onChange={(e) =>
                      updateSetting("batch_size", parseInt(e.target.value))
                    }
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Maximum File Size (MB)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={settings.max_file_size_mb}
                    onChange={(e) =>
                      updateSetting(
                        "max_file_size_mb",
                        parseInt(e.target.value),
                      )
                    }
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Maximum Files Per Check
                  </label>
                  <input
                    type="number"
                    min="2"
                    max="2000"
                    value={settings.max_files_per_job}
                    onChange={(e) =>
                      updateSetting(
                        "max_files_per_job",
                        parseInt(e.target.value),
                      )
                    }
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  />
                </div>
              </div>
            </>
          )}

          <div className="pt-4 border-t border-slate-100">
            {activeTab === "engine-config" ? (
              <button
                onClick={handleSaveEngineConfig}
                disabled={saving}
                className="px-6 py-2.5 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {saving ? "Saving..." : "Save Scoring Rules"}
              </button>
            ) : (
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-6 py-2.5 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : null}
                {saved ? "✓ Saved!" : "Save Settings"}
              </button>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
