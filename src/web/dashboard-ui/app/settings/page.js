'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useState } from 'react';

export default function SettingsPage() {
  const [threshold, setThreshold] = useState(0.5);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-2xl">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
          <p className="text-slate-500 mt-1">Configure default analysis parameters.</p>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-6">
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
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-brand-600"
              />
              <span className="text-lg font-bold text-brand-600 w-16 text-right">
                {(threshold * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-2">
              Pairs scoring above this threshold will be flagged for review.
            </p>
          </div>

          <div className="pt-4 border-t border-slate-100">
            <button
              onClick={handleSave}
              className="px-6 py-2.5 bg-brand-600 text-white font-semibold rounded-lg hover:bg-brand-700 transition-colors"
            >
              {saved ? 'Saved!' : 'Save Settings'}
            </button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
