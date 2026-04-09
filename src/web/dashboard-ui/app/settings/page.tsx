"use client";

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import {
  GlassCard,
  MagneticButton,
  TiltCard,
  FadeIn,
} from "@/components/Animation";
import { useState, useEffect } from "react";
import axios from "axios";

interface Settings {
  default_threshold: number;
  openai_api_key: string;
  openai_api_key_configured: boolean;
  openai_base_url: string;
  openai_model: string;
  anthropic_api_key: string;
  anthropic_api_key_configured: boolean;
  anthropic_model: string;
  embedding_runtime: string;
  embedding_model: string;
  embedding_server_url: string | null;
  embedding_server_host: string | null;
  embedding_server_port: number;
  embedding_device: string;
  embedding_batch_size: number;
  engine_weights: { [key: string]: number };
  batch_size: number;
  max_file_size_mb: number;
  max_files_per_job: number;
}

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saved, setSaved] = useState(false);
  const [activeTab, setActiveTab] = useState<
    "general" | "llm" | "engines" | "advanced"
  >("general");

  const enginePresets = [
    {
      name: "Balanced (Recommended)",
      description: "Good all-around performance for most use cases",
      weights: { token: 0.25, ast: 0.3, unixcoder: 0.3, structural: 0.15 },
    },
    {
      name: "Copy-Paste Detection",
      description:
        "Best for detecting direct copying, reformatting, minor changes",
      weights: { token: 0.4, ast: 0.25, unixcoder: 0.2, structural: 0.15 },
    },
    {
      name: "Semantic Similarity",
      description: "Detect logic similarity even with heavy obfuscation",
      weights: { token: 0.1, ast: 0.2, unixcoder: 0.55, structural: 0.15 },
    },
    {
      name: "Structure Focused",
      description: "Prioritize control flow and program structure patterns",
      weights: { token: 0.15, ast: 0.45, unixcoder: 0.2, structural: 0.2 },
    },
    {
      name: "Strict Comparison",
      description: "High sensitivity - highest false positive rate",
      weights: { token: 0.5, ast: 0.3, unixcoder: 0.15, structural: 0.05 },
    },
  ];

  useEffect(() => {
    if (authLoading || !user || user.role !== "admin") {
      return;
    }
    axios
      .get("/api/settings")
      .then((res) => setSettings(res.data))
      .catch(() => {});
  }, [authLoading, user]);

  const handleSave = () => {
    if (!settings) return;
    axios.patch("/api/settings", settings).then(() => {
      setSettings((current) => {
        if (!current) return current;
        return {
          ...current,
          openai_api_key: "",
          anthropic_api_key: "",
          openai_api_key_configured:
            current.openai_api_key_configured || current.openai_api_key.trim().length > 0,
          anthropic_api_key_configured:
            current.anthropic_api_key_configured || current.anthropic_api_key.trim().length > 0,
        };
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    });
  };

  const updateSetting = (key: keyof Settings, value: any) => {
    if (!settings) return;
    setSettings({ ...settings, [key]: value });
  };

  const updateEngineWeight = (engine: string, value: number) => {
    if (!settings) return;
    setSettings({
      ...settings,
      engine_weights: { ...settings.engine_weights, [engine]: value },
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

  const tabs = [
    { id: "general", label: "General" },
    { id: "llm", label: "LLM & AI" },
    { id: "engines", label: "Engines" },
    { id: "advanced", label: "Advanced" },
  ];

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
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                activeTab === tab.id
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
                      Saved to <code>.env.local</code>. The current key is never returned to the browser.
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
                      Saved to <code>.env.local</code>. The current key is never returned to the browser.
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
                </div>
              </div>
            </>
          )}

          {activeTab === "engines" && (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-3">
                  Engine Presets
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
                  {enginePresets.map((preset, idx) => (
                    <button
                      key={idx}
                      onClick={() =>
                        setSettings({
                          ...settings!,
                          engine_weights: preset.weights,
                        })
                      }
                      className={`p-4 border rounded-xl text-left transition-all hover:border-blue-400 hover:bg-blue-50 ${
                        Object.entries(settings.engine_weights).every(
                          ([k, v]) => Math.abs((preset.weights as Record<string, number>)[k] - v) < 0.01,
                        )
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
                  Custom Engine Weights
                </label>
                <p className="text-xs text-slate-400 mb-4">
                  Adjust contribution weights for each similarity engine. Total
                  should equal 1.0
                </p>
                <div className="space-y-4">
                  {Object.entries(settings.engine_weights).map(
                    ([engine, weight]) => (
                      <div key={engine} className="flex items-center gap-3">
                        <label className="w-24 text-sm font-medium text-slate-700 capitalize">
                          {engine}
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={weight}
                          onChange={(e) =>
                            updateEngineWeight(
                              engine,
                              parseFloat(e.target.value),
                            )
                          }
                          className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                        />
                        <span className="text-sm font-medium text-blue-600 w-12 text-right">
                          {(weight * 100).toFixed(0)}%
                        </span>
                      </div>
                    ),
                  )}
                </div>
              </div>
            </>
          )}

          {activeTab === "advanced" && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Batch Size
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
                    Max File Size (MB)
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
                    Max Files Per Job
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
            <button
              onClick={handleSave}
              className="px-6 py-2.5 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors"
            >
              {saved ? "✓ Saved!" : "Save Settings"}
            </button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
