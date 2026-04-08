'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useState, useCallback, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  BarChart3, Loader2, Trophy, FileUp, FolderArchive, X, AlertCircle,
  Zap, Target, Layers, TrendingUp, CheckCircle2, ChevronDown, ChevronUp,
  Download, Play, FlaskConical, FileText, ArrowRight, Square, Check,
  ChevronRight, UploadCloud, Database, Settings2, ClipboardList,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, RadarChart, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, Radar,
} from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const TOOLS = [
  { id: 'integritydesk', name: 'IntegrityDesk', desc: 'Multi-engine fusion (AST + N-gram + Winnowing + Embedding + Token)', color: '#0066cc', gradient: 'from-blue-500 to-blue-600', bgLight: 'bg-blue-50', ring: 'ring-blue-500', textColor: 'text-blue-600', engines: ['AST', 'N-gram', 'Winnowing', 'Embedding', 'Token', 'Execution'] },
  { id: 'moss', name: 'MOSS', desc: 'Token-based Jaccard similarity (Stanford)', color: '#7c3aed', gradient: 'from-violet-500 to-violet-600', bgLight: 'bg-violet-50', ring: 'ring-violet-500', textColor: 'text-violet-600', engines: ['Token'] },
  { id: 'jplag', name: 'JPlag', desc: 'AST structural comparison (KIT)', color: '#059669', gradient: 'from-emerald-500 to-emerald-600', bgLight: 'bg-emerald-50', ring: 'ring-emerald-500', textColor: 'text-emerald-600', engines: ['AST'] },
  { id: 'dolos', name: 'Dolos', desc: 'Winnowing fingerprint comparison', color: '#d97706', gradient: 'from-amber-500 to-amber-600', bgLight: 'bg-amber-50', ring: 'ring-amber-500', textColor: 'text-amber-600', engines: ['Winnowing'] },
  { id: 'nicad', name: 'NiCad', desc: 'Near-miss clone detector with normalization', color: '#e11d48', gradient: 'from-rose-500 to-rose-600', bgLight: 'bg-rose-50', ring: 'ring-rose-500', textColor: 'text-rose-600', engines: ['Normalization'] },
  { id: 'pmd', name: 'PMD CPD', desc: 'Copy/Paste duplicate token sequence detector', color: '#0f766e', gradient: 'from-teal-500 to-teal-600', bgLight: 'bg-teal-50', ring: 'ring-teal-500', textColor: 'text-teal-600', engines: ['Duplicate Blocks'] },
  { id: 'sherlock', name: 'Sherlock', desc: 'Line-level textual overlap detector', color: '#4f46e5', gradient: 'from-indigo-500 to-indigo-600', bgLight: 'bg-indigo-50', ring: 'ring-indigo-500', textColor: 'text-indigo-600', engines: ['Line Overlap'] },
  { id: 'sim', name: 'SIM', desc: 'Dick Grune text similarity tester', color: '#0891b2', gradient: 'from-cyan-500 to-cyan-600', bgLight: 'bg-cyan-50', ring: 'ring-cyan-500', textColor: 'text-cyan-600', engines: ['Text Similarity'] },
  { id: 'strange', name: 'STRANGE', desc: 'Semantic PDG clone detector', color: '#8b5cf6', gradient: 'from-purple-500 to-purple-600', bgLight: 'bg-purple-50', ring: 'ring-purple-500', textColor: 'text-purple-600', engines: ['PDG Analysis'] },
  { id: 'evalforge', name: 'EvalForge', desc: 'Plagiarism detection evaluation framework', color: '#f59e0b', gradient: 'from-orange-500 to-orange-600', bgLight: 'bg-orange-50', ring: 'ring-orange-500', textColor: 'text-orange-600', engines: ['Benchmark Runner'] },
  { id: 'gptzero', name: 'GPTZero', desc: 'Open source AI code/text detection', color: '#10b981', gradient: 'from-green-500 to-green-600', bgLight: 'bg-green-50', ring: 'ring-green-500', textColor: 'text-green-600', engines: ['Embedding Analysis'] },
  { id: 'codequiry', name: 'Codequiry', desc: 'Semantic embedding similarity', color: '#dc2626', gradient: 'from-red-500 to-red-600', bgLight: 'bg-red-50', ring: 'ring-red-500', textColor: 'text-red-600', engines: ['Embedding'] },
  { id: 'vendetect', name: 'Vendetect', desc: 'Cross-repository vendored code detection', color: '#ec4899', gradient: 'from-pink-500 to-pink-600', bgLight: 'bg-pink-50', ring: 'ring-pink-500', textColor: 'text-pink-600', engines: ['Cross Repo Matching'] },
];

const TEST_CASES = [
  { id: 'identical', label: 'Identical Files', desc: 'Two copies of the same file', expected: 0.95, codeA: `def calculate_average(data):\n    total = sum(data)\n    count = len(data)\n    return total / count\n\ndef find_max(data):\n    max_val = data[0]\n    for item in data:\n        if item > max_val:\n            max_val = item\n    return max_val`, codeB: `def calculate_average(data):\n    total = sum(data)\n    count = len(data)\n    return total / count\n\ndef find_max(data):\n    max_val = data[0]\n    for item in data:\n        if item > max_val:\n            max_val = item\n    return max_val` },
  { id: 'renamed', label: 'Renamed Variables', desc: 'Same logic, different variable/function names', expected: 0.80, codeA: `def calculate_average(data):\n    total = sum(data)\n    count = len(data)\n    return total / count`, codeB: `def compute_mean(values):\n    total = sum(values)\n    count = len(values)\n    return total / count` },
  { id: 'reordered', label: 'Reordered Functions', desc: 'Same functions in different order', expected: 0.70, codeA: `def calc_avg(data):\n    return sum(data)/len(data)\n\ndef find_max(data):\n    return max(data)`, codeB: `def find_max(data):\n    return max(data)\n\ndef calc_avg(data):\n    return sum(data)/len(data)` },
  { id: 'similar', label: 'Similar Logic', desc: 'Same algorithm, different style', expected: 0.50, codeA: `def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr`, codeB: `def sort_array(data):\n    n = len(data)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if data[j] > data[j+1]:\n                data[j], data[j+1] = data[j+1], data[j]\n    return data` },
  { id: 'unrelated', label: 'Unrelated Files', desc: 'Completely different code', expected: 0.10, codeA: `import numpy as np\ndef sharpe_ratio(returns, risk_free_rate=0.02):\n    excess_returns = returns - risk_free_rate\n    return np.mean(excess_returns) / np.std(excess_returns)`, codeB: `from flask import Flask\napp = Flask(__name__)\n@app.route('/users')\ndef get_users():\n    return 'users'` },
];

const DATASETS = [
  { id: 'basic-clone', name: 'Basic Clone Detection', desc: '5 test cases: identical, renamed, reordered, similar, and unrelated code pairs', icon: '🧪', color: 'blue', cases: TEST_CASES },
  {
    id: 'obfuscation', name: 'Obfuscation Resistance', desc: 'Tests how well tools detect plagiarism through variable renaming, reordering, and comment changes', icon: '🔍', color: 'violet', cases: [
      { id: 'obf-rename', label: 'Variable Renaming', desc: 'All identifiers renamed, same logic', expected: 0.80, codeA: `def calculate_average(data):\n    total = sum(data)\n    count = len(data)\n    return total / count`, codeB: `def compute_mean(values):\n    total = sum(values)\n    cnt = len(values)\n    return total / cnt` },
      { id: 'obf-reorder', label: 'Function Reordering', desc: 'Same functions in different order', expected: 0.70, codeA: `def factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n-1)\n\ndef is_prime(n):\n    if n < 2: return False\n    for i in range(2, int(n**0.5)+1):\n        if n % i == 0: return False\n    return True`, codeB: `def is_prime(n):\n    if n < 2: return False\n    for i in range(2, int(n**0.5)+1):\n        if n % i == 0: return False\n    return True\n\ndef factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n-1)` },
      { id: 'obf-comments', label: 'Comment/Whitespace Changes', desc: 'Added comments and blank lines', expected: 0.90, codeA: `def binary_search(arr, target):\n    left, right = 0, len(arr)-1\n    while left <= right:\n        mid = (left+right)//2\n        if arr[mid] == target: return mid\n        elif arr[mid] < target: left = mid+1\n        else: right = mid-1\n    return -1`, codeB: `# Binary search implementation\ndef binary_search(arr, target):\n    # Initialize boundaries\n    left, right = 0, len(arr)-1\n    while left <= right:\n        mid = (left+right)//2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            left = mid+1\n        else:\n            right = mid-1\n    return -1` },
    ]
  },
  {
    id: 'multi-file', name: 'Multi-File Class', desc: 'Simulated class of 6 student submissions with varying similarity levels', icon: '👥', color: 'emerald', cases: [
      { id: 'class-1-2', label: 'Student 1 vs Student 2', desc: 'Direct copy with renamed variables', expected: 0.85, codeA: `class Stack:\n    def __init__(self):\n        self.items = []\n    def push(self, item):\n        self.items.append(item)\n    def pop(self):\n        return self.items.pop()`, codeB: `class Stack:\n    def __init__(self):\n        self.elements = []\n    def push(self, element):\n        self.elements.append(element)\n    def pop(self):\n        return self.elements.pop()` },
      { id: 'class-3-4', label: 'Student 3 vs Student 4', desc: 'Similar algorithm, different style', expected: 0.55, codeA: `def linear_search(arr, target):\n    for i in range(len(arr)):\n        if arr[i] == target: return i\n    return -1`, codeB: `def search_list(data, key):\n    index = 0\n    while index < len(data):\n        if data[index] == key: return index\n        index += 1\n    return -1` },
      { id: 'class-5-6', label: 'Student 5 vs Student 6', desc: 'Completely different implementations', expected: 0.15, codeA: `def merge_sort(arr):\n    if len(arr) <= 1: return arr\n    mid = len(arr) // 2\n    return merge(merge_sort(arr[:mid]), merge_sort(arr[mid:]))`, codeB: `def quick_sort(arr):\n    if len(arr) <= 1: return arr\n    pivot = arr[len(arr)//2]\n    return quick_sort([x for x in arr if x < pivot]) + [pivot] + quick_sort([x for x in arr if x > pivot])` },
    ]
  },
  {
    id: 'java-clone', name: 'Java Clone Detection', desc: 'Java code pairs testing clone detection across languages', icon: '☕', color: 'amber', cases: [
      { id: 'java-identical', label: 'Identical Java', desc: 'Two copies of the same Java class', expected: 0.95, codeA: `public class Calculator {\n    public int add(int a, int b) { return a + b; }\n    public int subtract(int a, int b) { return a - b; }\n}`, codeB: `public class Calculator {\n    public int add(int a, int b) { return a + b; }\n    public int subtract(int a, int b) { return a - b; }\n}` },
      { id: 'java-renamed', label: 'Renamed Java Methods', desc: 'Same logic with renamed methods', expected: 0.75, codeA: `public class LinkedList {\n    private Node head;\n    public void insert(int data) {\n        Node newNode = new Node(data);\n        newNode.next = head;\n        head = newNode;\n    }\n}`, codeB: `public class SingleList {\n    private Node first;\n    public void add(int value) {\n        Node node = new Node(value);\n        node.next = first;\n        first = node;\n    }\n}` },
    ]
  },
];

const TOOL_COLORS = Object.fromEntries(TOOLS.map(t => [t.id, t.color]));

// ── Step indicator ──────────────────────────────────────────────────────────
function StepIndicator({ steps, currentStep, completedSteps }) {
  return (
    <div className="flex items-center gap-0 mb-8">
      {steps.map((step, idx) => {
        const isCompleted = completedSteps.includes(idx);
        const isCurrent = currentStep === idx;
        const isLast = idx === steps.length - 1;
        return (
          <div key={idx} className="flex items-center flex-1 last:flex-none">
            <div className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
              isCurrent ? 'bg-violet-600 shadow-lg shadow-violet-500/25' :
              isCompleted ? 'bg-emerald-50 border border-emerald-200' :
              'bg-white border border-slate-200'
            }`}>
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                isCurrent ? 'bg-white/20 text-white' :
                isCompleted ? 'bg-emerald-500 text-white' :
                'bg-slate-100 text-slate-400'
              }`}>
                {isCompleted ? <Check size={13} /> : idx + 1}
              </div>
              <div>
                <div className={`text-xs font-bold uppercase tracking-wide ${
                  isCurrent ? 'text-white' : isCompleted ? 'text-emerald-700' : 'text-slate-400'
                }`}>{step.label}</div>
                <div className={`text-xs mt-0.5 hidden sm:block ${
                  isCurrent ? 'text-violet-200' : isCompleted ? 'text-emerald-500' : 'text-slate-400'
                }`}>{step.subtitle}</div>
              </div>
            </div>
            {!isLast && (
              <div className={`h-px flex-1 mx-2 ${
                completedSteps.includes(idx) ? 'bg-emerald-300' : 'bg-slate-200'
              }`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Step 1: Tool Selection ──────────────────────────────────────────────────
function ToolSelectionStep({ selectedTools, setSelectedTools, onNext }) {
  const toggleTool = (id) => setSelectedTools(prev =>
    prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
  );

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <Settings2 size={18} className="text-violet-500" />
            Select Detection Tools
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">Choose which tools to include in the benchmark</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-sm font-semibold px-3 py-1.5 rounded-lg ${
            selectedTools.length > 0 ? 'bg-violet-50 text-violet-700' : 'bg-slate-100 text-slate-400'
          }`}>{selectedTools.length} / {TOOLS.length} selected</span>
          <div className="flex gap-1">
            <button onClick={() => setSelectedTools(TOOLS.map(t => t.id))} className="text-xs font-medium text-blue-600 hover:text-blue-700 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors">All</button>
            <button onClick={() => setSelectedTools([])} className="text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">Clear</button>
          </div>
        </div>
      </div>
      <div className="p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {TOOLS.map(tool => {
            const isSelected = selectedTools.includes(tool.id);
            return (
              <button key={tool.id} onClick={() => toggleTool(tool.id)}
                className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 group ${
                  isSelected
                    ? `border-transparent ring-2 ${tool.ring} ring-offset-2 ${tool.bgLight}`
                    : 'border-slate-200 hover:border-slate-300 bg-white hover:shadow-sm'
                }`}>
                {isSelected && (
                  <div className="absolute top-2 right-2">
                    <CheckCircle2 size={16} className={tool.textColor} />
                  </div>
                )}
                <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${tool.gradient} flex items-center justify-center mb-3 shadow-sm`}>
                  <Zap size={16} className="text-white" />
                </div>
                <div className="font-semibold text-sm text-slate-900">{tool.name}</div>
                <div className="text-xs text-slate-400 mt-0.5 line-clamp-2">{tool.desc}</div>
              </button>
            );
          })}
        </div>
      </div>
      <div className="px-6 pb-6 flex justify-end">
        <button onClick={onNext} disabled={selectedTools.length === 0}
          className="flex items-center gap-2 px-6 py-3 bg-violet-600 hover:bg-violet-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-semibold rounded-xl transition-all shadow-lg shadow-violet-500/25 hover:shadow-xl disabled:shadow-none">
          Continue to Dataset
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}

// ── Step 2: Dataset Selection ───────────────────────────────────────────────
function DatasetStep({ selectedDataset, setSelectedDataset, uploadMode, setUploadMode, files, setFiles, benchmarkDatasets, onBack, onNext }) {
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setFiles(Array.from(e.dataTransfer.files));
  }, [setFiles]);

  const handleDragOver = (e) => e.preventDefault();

  const activeDataset = DATASETS.find(d => d.id === selectedDataset);
  const canProceed = uploadMode === 'builtin' ? !!selectedDataset :
    uploadMode === 'individual' ? files.length >= 2 :
    files.length >= 1;

  return (
    <div className="space-y-5">
      {/* Mode tabs */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <Database size={18} className="text-violet-500" />
            Choose Dataset
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">Use a built-in benchmark dataset or upload your own files</p>
        </div>
        <div className="flex border-b border-slate-100">
          {[
            { id: 'builtin', label: 'Built-in Datasets', icon: FlaskConical },
            { id: 'individual', label: 'Upload Files', icon: FileUp },
            { id: 'zip', label: 'Upload ZIP', icon: FolderArchive },
          ].map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => { setUploadMode(id); setFiles([]); if (id !== 'builtin') setSelectedDataset(null); }}
              className={`flex items-center gap-2 px-5 py-3.5 text-sm font-medium border-b-2 transition-colors ${
                uploadMode === id ? 'border-violet-500 text-violet-700 bg-violet-50/50' : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}>
              <Icon size={15} />
              {label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {uploadMode === 'builtin' && (
            <div className="space-y-5">
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Built-in Test Suites</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {DATASETS.map(ds => {
                    const isActive = selectedDataset === ds.id;
                    return (
                      <button key={ds.id} onClick={() => setSelectedDataset(ds.id)}
                        className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 ${
                          isActive ? 'border-violet-400 bg-violet-50 ring-2 ring-violet-500/20' : 'border-slate-200 hover:border-slate-300 bg-white hover:shadow-md'
                        }`}>
                        {isActive && <div className="absolute top-2 right-2"><CheckCircle2 size={14} className="text-violet-600" /></div>}
                        <div className="text-xl mb-2">{ds.icon}</div>
                        <div className="font-semibold text-sm text-slate-900">{ds.name}</div>
                        <div className="text-xs text-slate-500 mt-1 line-clamp-2">{ds.desc}</div>
                        <div className="text-xs font-medium text-violet-600 mt-2">{ds.cases.length} test cases</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {benchmarkDatasets.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Benchmark Datasets</p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {benchmarkDatasets.map(ds => {
                      const isActive = selectedDataset === ds.id;
                      return (
                        <button key={ds.id} onClick={() => setSelectedDataset(ds.id)}
                          className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 ${
                            isActive ? 'border-emerald-400 bg-emerald-50 ring-2 ring-emerald-500/20' : 'border-slate-200 hover:border-slate-300 bg-white hover:shadow-md'
                          }`}>
                          {isActive && <div className="absolute top-2 right-2"><CheckCircle2 size={14} className="text-emerald-600" /></div>}
                          <div className="text-xl mb-2">{ds.icon}</div>
                          <div className="font-semibold text-sm text-slate-900">{ds.name}</div>
                          <div className="text-xs text-slate-500 mt-1 line-clamp-2">{ds.desc}</div>
                          <div className="text-xs font-medium text-emerald-600 mt-2 flex items-center gap-2">
                            {ds.language && <span>{ds.language.toUpperCase()}</span>}
                            {ds.size && <><span className="text-slate-300">•</span><span>{ds.size}</span></>}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {activeDataset && (
                <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Test cases in "{activeDataset.name}"</p>
                  <div className="grid md:grid-cols-3 gap-2">
                    {activeDataset.cases.map(tc => (
                      <div key={tc.id} className="flex items-center gap-2 bg-white rounded-lg border border-slate-200 px-3 py-2.5">
                        <div className={`w-2 h-2 rounded-full shrink-0 ${
                          tc.expected >= 0.9 ? 'bg-red-500' : tc.expected >= 0.7 ? 'bg-amber-500' : tc.expected >= 0.4 ? 'bg-yellow-500' : 'bg-emerald-500'
                        }`} />
                        <div className="min-w-0">
                          <div className="text-xs font-semibold text-slate-800 truncate">{tc.label}</div>
                          <div className="text-xs text-slate-400">~{(tc.expected * 100).toFixed(0)}% expected</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {(uploadMode === 'individual' || uploadMode === 'zip') && (
            <div>
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => document.getElementById('file-input').click()}
                className="border-2 border-dashed border-slate-300 rounded-2xl p-10 text-center cursor-pointer hover:border-violet-400 hover:bg-violet-50/30 transition-all group"
              >
                <input id="file-input" type="file" className="hidden" multiple={uploadMode === 'individual'}
                  accept={uploadMode === 'zip' ? '.zip' : undefined}
                  onChange={e => setFiles(Array.from(e.target.files))} />
                <UploadCloud size={40} className="mx-auto text-slate-300 group-hover:text-violet-400 transition-colors mb-4" />
                <p className="font-semibold text-slate-600 mb-1">
                  {uploadMode === 'zip' ? 'Drop a ZIP archive here' : 'Drop files here'}
                </p>
                <p className="text-sm text-slate-400">
                  {uploadMode === 'individual' ? 'Upload 2 or more source files to compare' : 'ZIP containing source files for bulk comparison'}
                </p>
                <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-600 group-hover:border-violet-300 transition-colors">
                  <FileUp size={14} />
                  Browse files
                </div>
              </div>

              {files.length > 0 && (
                <div className="mt-4 bg-slate-50 rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-3 px-4 py-2.5 group/file hover:bg-white transition-colors">
                      <div className="w-6 h-6 rounded-md bg-emerald-100 flex items-center justify-center shrink-0">
                        <FileUp size={12} className="text-emerald-600" />
                      </div>
                      <span className="text-sm font-medium text-slate-700 truncate flex-1">{f.name}</span>
                      <span className="text-xs text-slate-400 shrink-0">{(f.size / 1024).toFixed(1)} KB</span>
                      <button onClick={() => setFiles(files.filter((_, j) => j !== i))} className="opacity-0 group-hover/file:opacity-100 text-slate-300 hover:text-red-500 transition-all">
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {uploadMode === 'individual' && files.length > 0 && files.length < 2 && (
                <p className="text-xs text-amber-600 mt-2 flex items-center gap-1.5">
                  <AlertCircle size={13} /> Upload at least 2 files to compare
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-600 hover:text-slate-800 font-medium rounded-xl hover:border-slate-300 transition-all text-sm">
          ← Back
        </button>
        <button onClick={onNext} disabled={!canProceed}
          className="flex items-center gap-2 px-6 py-3 bg-violet-600 hover:bg-violet-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-semibold rounded-xl transition-all shadow-lg shadow-violet-500/25 hover:shadow-xl disabled:shadow-none">
          Ready to Run
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}

// ── Step 3: Run ─────────────────────────────────────────────────────────────
function RunStep({ selectedTools, selectedDataset, uploadMode, files, benchmarkDatasets, onBack, onComplete }) {
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState('');
  const [progressPct, setProgressPct] = useState(0);
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);
  const cancelRef = useRef(false);

  const activeDataset = DATASETS.find(d => d.id === selectedDataset) ||
    benchmarkDatasets.find(d => d.id === selectedDataset);

  const toolNames = selectedTools.map(id => TOOLS.find(t => t.id === id)?.name).filter(Boolean);

  const run = async () => {
    cancelRef.current = false;
    setError('');
    setRunning(true);
    setResults(null);
    setProgressPct(10);

    try {
      if (uploadMode === 'builtin' && activeDataset?.cases) {
        // Run all test cases in the built-in dataset
        const allResults = [];
        const cases = activeDataset.cases;

        for (let i = 0; i < cases.length; i++) {
          if (cancelRef.current) break;
          const tc = cases[i];
          setProgress(`Running "${tc.label}" (${i + 1}/${cases.length})…`);
          setProgressPct(10 + ((i / cases.length) * 80));

          const blobA = new Blob([tc.codeA], { type: 'text/plain' });
          const blobB = new Blob([tc.codeB], { type: 'text/plain' });
          const fileA = new File([blobA], `${tc.id}_a.py`);
          const fileB = new File([blobB], `${tc.id}_b.py`);

          const formData = new FormData();
          formData.append('files', fileA);
          formData.append('files', fileB);
          selectedTools.forEach(t => formData.append('tools', t));

          try {
            const res = await axios.post(`${API}/api/benchmark`, formData, {
              headers: { 'Content-Type': 'multipart/form-data' },
            });
            allResults.push({ testCase: tc, ...res.data });
          } catch (err) {
            // Continue with other cases
          }
        }

        if (!cancelRef.current && allResults.length > 0) {
          setProgressPct(100);
          setProgress('Complete!');
          // Merge results
          const merged = allResults[0];
          merged.pair_results = allResults.flatMap(r => r.pair_results || []);
          setResults({ ...merged, datasetName: activeDataset.name, runAt: new Date().toISOString() });
          setTimeout(() => onComplete({ ...merged, datasetName: activeDataset.name, runAt: new Date().toISOString() }), 400);
        }
      } else {
        // Upload mode
        setProgress('Uploading files…');
        setProgressPct(20);
        const formData = new FormData();
        files.forEach(f => formData.append('files', f));
        selectedTools.forEach(t => formData.append('tools', t));

        setProgress('Running analysis across all tools…');
        setProgressPct(50);
        const res = await axios.post(`${API}/api/benchmark`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        setProgressPct(100);
        setProgress('Complete!');
        setResults({ ...res.data, runAt: new Date().toISOString() });
        setTimeout(() => onComplete({ ...res.data, runAt: new Date().toISOString() }), 400);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Benchmark failed. Please try again.');
    }

    if (!cancelRef.current) setRunning(false);
  };

  const stop = () => {
    cancelRef.current = true;
    setRunning(false);
    setProgress('');
    setProgressPct(0);
  };

  return (
    <div className="space-y-5">
      {/* Summary card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="font-semibold text-slate-900 flex items-center gap-2 mb-5">
          <ClipboardList size={18} className="text-violet-500" />
          Benchmark Configuration
        </h2>
        <div className="grid md:grid-cols-3 gap-4">
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Tools</p>
            <div className="flex flex-wrap gap-1.5">
              {selectedTools.slice(0, 6).map(id => {
                const t = TOOLS.find(x => x.id === id);
                return t ? (
                  <span key={id} className={`text-xs font-medium px-2.5 py-1 rounded-lg ${t.bgLight} ${t.textColor}`}>{t.name}</span>
                ) : null;
              })}
              {selectedTools.length > 6 && (
                <span className="text-xs font-medium px-2.5 py-1 rounded-lg bg-slate-200 text-slate-600">+{selectedTools.length - 6} more</span>
              )}
            </div>
          </div>
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Dataset</p>
            {uploadMode === 'builtin' ? (
              <>
                <p className="font-semibold text-slate-800 text-sm">{activeDataset?.name || 'Unknown'}</p>
                <p className="text-xs text-slate-500 mt-1">{activeDataset?.cases?.length || 0} test cases</p>
              </>
            ) : (
              <>
                <p className="font-semibold text-slate-800 text-sm">{files.length} uploaded file{files.length !== 1 ? 's' : ''}</p>
                <p className="text-xs text-slate-500 mt-1">{uploadMode === 'zip' ? 'ZIP archive' : 'Individual files'}</p>
              </>
            )}
          </div>
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Estimated Time</p>
            <p className="font-semibold text-slate-800 text-sm">~{Math.ceil(selectedTools.length * ((activeDataset?.cases?.length || files.length) || 1) * 0.5)}s</p>
            <p className="text-xs text-slate-500 mt-1">{selectedTools.length} tools × {activeDataset?.cases?.length || files.length || 1} pairs</p>
          </div>
        </div>
      </div>

      {/* Run control */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        {error && (
          <div className="mb-4 flex items-start gap-3 p-4 bg-red-50 border border-red-100 rounded-xl">
            <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {running && (
          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-slate-700 flex items-center gap-2">
                <Loader2 size={15} className="text-violet-600 animate-spin" />
                {progress}
              </p>
              <span className="text-sm font-bold text-violet-600">{Math.round(progressPct)}%</span>
            </div>
            <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-violet-500 to-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          {!running ? (
            <button onClick={run}
              className="flex-1 flex items-center justify-center gap-3 py-4 bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-700 hover:to-blue-700 text-white font-bold rounded-xl transition-all shadow-lg shadow-violet-500/25 hover:shadow-xl text-base">
              <Play size={20} />
              Start Benchmark
            </button>
          ) : (
            <button onClick={stop}
              className="flex-1 flex items-center justify-center gap-3 py-4 bg-red-500 hover:bg-red-600 text-white font-bold rounded-xl transition-all shadow-lg shadow-red-500/25 text-base">
              <Square size={18} />
              Stop
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <button onClick={onBack} disabled={running} className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-600 hover:text-slate-800 font-medium rounded-xl hover:border-slate-300 transition-all text-sm disabled:opacity-50">
          ← Back
        </button>
      </div>
    </div>
  );
}

// ── Step 4: Report ──────────────────────────────────────────────────────────
function ReportStep({ results, onRestart }) {
  const [expandedPairs, setExpandedPairs] = useState({});
  const { tool_scores, pair_results, summary } = results;
  const activeTools = Object.keys(tool_scores || {});

  const chartData = (pair_results || []).map(pair => {
    const d = { pair: pair.label };
    activeTools.forEach(t => {
      const tr = pair.tool_results?.find(r => r.tool === t);
      d[t] = tr ? Math.round(tr.score * 1000) / 10 : 0;
    });
    return d;
  });

  const radarData = activeTools.map(tool => {
    const d = { tool: TOOLS.find(t => t.id === tool)?.name || tool };
    (pair_results || []).forEach(pair => {
      const tr = pair.tool_results?.find(r => r.tool === tool);
      d[pair.label] = tr ? Math.round(tr.score * 1000) / 10 : 0;
    });
    return d;
  });

  const togglePair = (idx) => setExpandedPairs(prev => ({ ...prev, [idx]: !prev[idx] }));

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `benchmark-report-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadCSV = () => {
    const rows = [['Pair', 'File A', 'File B', ...activeTools.map(id => TOOLS.find(t => t.id === id)?.name || id), 'Max Score', 'Min Score']];
    (pair_results || []).forEach(pair => {
      const scores = activeTools.map(t => {
        const tr = pair.tool_results?.find(r => r.tool === t);
        return tr ? (tr.score * 100).toFixed(1) : 'N/A';
      });
      const numScores = scores.filter(s => s !== 'N/A').map(Number);
      rows.push([pair.label, pair.file_a || '', pair.file_b || '', ...scores,
        numScores.length ? Math.max(...numScores).toFixed(1) : 'N/A',
        numScores.length ? Math.min(...numScores).toFixed(1) : 'N/A',
      ]);
    });
    const csv = rows.map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `benchmark-report-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Report header */}
      <div className="bg-gradient-to-r from-violet-50 to-blue-50 border border-violet-200 rounded-2xl p-5 flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
            <FileText size={20} className="text-violet-600" />
          </div>
          <div>
            <p className="font-bold text-violet-900">{results.datasetName || 'Benchmark'} Report</p>
            <p className="text-sm text-violet-600 mt-0.5">
              Generated {results.runAt ? new Date(results.runAt).toLocaleString() : 'just now'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={downloadCSV}
            className="flex items-center gap-2 px-4 py-2.5 bg-white border border-violet-200 hover:border-violet-400 text-violet-700 font-semibold rounded-xl transition-all text-sm hover:shadow-sm">
            <Download size={15} />
            CSV
          </button>
          <button onClick={downloadJSON}
            className="flex items-center gap-2 px-4 py-2.5 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-xl transition-all text-sm shadow-lg shadow-violet-500/25">
            <Download size={15} />
            JSON
          </button>
          <button onClick={onRestart}
            className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 hover:border-slate-300 text-slate-600 font-semibold rounded-xl transition-all text-sm">
            New Benchmark
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { icon: Layers, bg: 'bg-blue-50', color: 'text-blue-600', label: 'Tools Run', value: summary?.tools_compared || activeTools.length },
          { icon: Target, bg: 'bg-emerald-50', color: 'text-emerald-600', label: 'Pairs Tested', value: summary?.pairs_tested || (pair_results?.length || 0) },
          { icon: TrendingUp, bg: 'bg-violet-50', color: 'text-violet-600', label: 'IntegrityDesk Avg', value: summary?.accuracy?.integritydesk ? `${(summary.accuracy.integritydesk * 100).toFixed(1)}%` : '—' },
          { icon: Trophy, bg: 'bg-amber-50', color: 'text-amber-600', label: 'Best Competitor', value: summary?.accuracy?.best_competitor ? `${(summary.accuracy.best_competitor * 100).toFixed(1)}%` : '—' },
        ].map(({ icon: Icon, bg, color, label, value }) => (
          <div key={label} className="bg-white rounded-2xl border border-slate-200 p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className={`w-9 h-9 rounded-xl ${bg} flex items-center justify-center`}>
                <Icon size={18} className={color} />
              </div>
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</span>
            </div>
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      {chartData.length > 0 && (
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Score Comparison</h2>
              <p className="text-sm text-slate-500 mt-0.5">Similarity scores per file pair</p>
            </div>
            <div className="p-6 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="pair" tick={{ fontSize: 11, fill: '#64748b' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} domain={[0, 100]} />
                  <Tooltip formatter={v => `${v.toFixed(1)}%`} contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                  <Legend wrapperStyle={{ fontSize: '12px' }} />
                  {activeTools.map(tool => (
                    <Bar key={tool} dataKey={tool} fill={TOOL_COLORS[tool] || '#94a3b8'} radius={[4, 4, 0, 0]} name={TOOLS.find(t => t.id === tool)?.name || tool} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Tool Radar</h2>
              <p className="text-sm text-slate-500 mt-0.5">Multi-dimensional tool comparison</p>
            </div>
            <div className="p-6 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="tool" tick={{ fontSize: 11, fill: '#64748b' }} />
                  <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <Tooltip formatter={v => `${v.toFixed(1)}%`} />
                  <Legend wrapperStyle={{ fontSize: '12px' }} />
                  {(pair_results || []).map((pair, i) => (
                    <Radar key={pair.label} name={pair.label} dataKey={pair.label}
                      stroke={TOOL_COLORS.integritydesk} fill={TOOL_COLORS.integritydesk}
                      fillOpacity={0.1 + i * 0.1} />
                  ))}
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Detailed table */}
      {(pair_results?.length || 0) > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-5 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900">Detailed Pair Results</h2>
            <p className="text-sm text-slate-500 mt-0.5">Click any pair to expand individual tool scores</p>
          </div>
          <div className="hidden lg:grid px-6 py-3 bg-slate-50/80 text-[11px] uppercase tracking-wider text-slate-400 font-semibold"
            style={{ gridTemplateColumns: `2fr repeat(${activeTools.length}, 1fr) 60px 60px 70px` }}>
            <div>File Pair</div>
            {activeTools.map(tool => (
              <div key={tool} className="text-center flex items-center justify-center gap-1.5">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: TOOL_COLORS[tool] }} />
                {TOOLS.find(t => t.id === tool)?.name || tool}
              </div>
            ))}
            <div className="text-center">Max</div>
            <div className="text-center">Min</div>
            <div className="text-center">Spread</div>
          </div>
          <div className="divide-y divide-slate-50">
            {(pair_results || []).map((pair, idx) => {
              const scores = activeTools.map(t => {
                const tr = pair.tool_results?.find(r => r.tool === t);
                return tr ? tr.score : null;
              });
              const valid = scores.filter(s => s !== null);
              const maxScore = valid.length ? Math.max(...valid) : 0;
              const minScore = valid.length ? Math.min(...valid) : 0;
              const spread = maxScore - minScore;
              const isExpanded = expandedPairs[idx];

              return (
                <div key={idx}>
                  <button onClick={() => togglePair(idx)}
                    className="w-full px-6 py-4 hover:bg-slate-50/50 transition-colors text-left hidden lg:grid items-center"
                    style={{ gridTemplateColumns: `2fr repeat(${activeTools.length}, 1fr) 60px 60px 70px` }}>
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-8 rounded-full ${maxScore >= 0.9 ? 'bg-red-500' : maxScore >= 0.75 ? 'bg-amber-500' : maxScore >= 0.5 ? 'bg-yellow-500' : 'bg-emerald-500'}`} />
                      <div>
                        <div className="text-sm font-semibold text-slate-900">{pair.label}</div>
                        <div className="text-xs text-slate-400">{pair.file_a} vs {pair.file_b}</div>
                      </div>
                      {isExpanded ? <ChevronUp size={14} className="text-slate-400 ml-2" /> : <ChevronDown size={14} className="text-slate-400 ml-2" />}
                    </div>
                    {activeTools.map((tool, ti) => {
                      const score = scores[ti];
                      return (
                        <div key={tool} className="text-center">
                          {score !== null ? (
                            <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold ${tool === 'integritydesk' ? 'bg-blue-50 text-blue-700' : 'bg-slate-50 text-slate-600'}`}>
                              {(score * 100).toFixed(1)}%
                            </span>
                          ) : <span className="text-xs text-slate-300">N/A</span>}
                        </div>
                      );
                    })}
                    <div className="text-center text-xs font-bold text-red-600">{(maxScore * 100).toFixed(0)}%</div>
                    <div className="text-center text-xs font-bold text-emerald-600">{(minScore * 100).toFixed(0)}%</div>
                    <div className={`text-center text-xs font-bold ${spread >= 0.3 ? 'text-red-600' : 'text-emerald-600'}`}>{(spread * 100).toFixed(0)}%</div>
                  </button>
                  {/* Mobile row */}
                  <button onClick={() => togglePair(idx)} className="lg:hidden w-full px-4 py-3 hover:bg-slate-50/50 text-left flex items-center gap-3">
                    <div className={`w-2 h-8 rounded-full shrink-0 ${maxScore >= 0.9 ? 'bg-red-500' : maxScore >= 0.75 ? 'bg-amber-500' : maxScore >= 0.5 ? 'bg-yellow-500' : 'bg-emerald-500'}`} />
                    <div className="flex-1">
                      <div className="text-sm font-semibold text-slate-900">{pair.label}</div>
                      <div className="text-xs text-slate-400">Max: {(maxScore * 100).toFixed(0)}% · Min: {(minScore * 100).toFixed(0)}%</div>
                    </div>
                    {isExpanded ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
                  </button>

                  {isExpanded && (
                    <div className="px-6 pb-5 bg-slate-50/50">
                      <div className="grid md:grid-cols-2 gap-3 mt-3">
                        {pair.tool_results?.map(tr => {
                          const toolInfo = TOOLS.find(t => t.id === tr.tool);
                          if (!toolInfo) return null;
                          return (
                            <div key={tr.tool} className="bg-white rounded-xl border border-slate-200 p-4">
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                  <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${toolInfo.gradient} flex items-center justify-center`}>
                                    <Zap size={13} className="text-white" />
                                  </div>
                                  <span className="text-sm font-semibold text-slate-900">{toolInfo.name}</span>
                                </div>
                                <span className={`text-lg font-bold ${toolInfo.textColor}`}>{(tr.score * 100).toFixed(1)}%</span>
                              </div>
                              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                <div className="h-full rounded-full transition-all duration-500"
                                  style={{ width: `${tr.score * 100}%`, background: `linear-gradient(90deg, ${toolInfo.color}, ${toolInfo.color}dd)` }} />
                              </div>
                              <div className="flex items-center justify-between mt-2">
                                <span className={`text-xs font-medium ${tr.score >= 0.9 ? 'text-red-600' : tr.score >= 0.75 ? 'text-amber-600' : tr.score >= 0.5 ? 'text-yellow-600' : 'text-emerald-600'}`}>
                                  {tr.score >= 0.9 ? 'Critical risk' : tr.score >= 0.75 ? 'High risk' : tr.score >= 0.5 ? 'Medium risk' : 'Low risk'}
                                </span>
                                <span className="text-xs text-slate-400">{toolInfo.desc}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────
export default function BenchmarkPage() {
  const [step, setStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [selectedTools, setSelectedTools] = useState(TOOLS.map(t => t.id));
  const [selectedDataset, setSelectedDataset] = useState('basic-clone');
  const [uploadMode, setUploadMode] = useState('builtin');
  const [files, setFiles] = useState([]);
  const [benchmarkDatasets, setBenchmarkDatasets] = useState([]);
  const [results, setResults] = useState(null);

  useEffect(() => {
    axios.get(`${API}/api/benchmark-datasets`).then(res => {
      if (res.data?.datasets) setBenchmarkDatasets(res.data.datasets);
    }).catch(() => {});
  }, []);

  const goToStep = (next, currentCompleted) => {
    setCompletedSteps(prev => {
      const updated = [...new Set([...prev, currentCompleted])];
      return updated;
    });
    setStep(next);
  };

  const STEPS = [
    { label: 'Select Tools', subtitle: 'Choose what to benchmark' },
    { label: 'Dataset', subtitle: 'Pick or upload data' },
    { label: 'Run', subtitle: 'Execute the benchmark' },
    { label: 'Report', subtitle: 'View & download results' },
  ];

  const restart = () => {
    setStep(0);
    setCompletedSteps([]);
    setResults(null);
  };

  return (
    <DashboardLayout>
      <div className="p-4 lg:p-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-lg shadow-violet-500/25 shrink-0">
            <FlaskConical size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Benchmark Suite</h1>
            <p className="text-slate-500 text-sm mt-0.5">Compare plagiarism detection tools across standardized datasets.</p>
          </div>
        </div>

        {/* Stepper */}
        <StepIndicator steps={STEPS} currentStep={step} completedSteps={completedSteps} />

        {/* Steps */}
        {step === 0 && (
          <ToolSelectionStep
            selectedTools={selectedTools}
            setSelectedTools={setSelectedTools}
            onNext={() => goToStep(1, 0)}
          />
        )}

        {step === 1 && (
          <DatasetStep
            selectedDataset={selectedDataset}
            setSelectedDataset={setSelectedDataset}
            uploadMode={uploadMode}
            setUploadMode={setUploadMode}
            files={files}
            setFiles={setFiles}
            benchmarkDatasets={benchmarkDatasets}
            onBack={() => setStep(0)}
            onNext={() => goToStep(2, 1)}
          />
        )}

        {step === 2 && (
          <RunStep
            selectedTools={selectedTools}
            selectedDataset={selectedDataset}
            uploadMode={uploadMode}
            files={files}
            benchmarkDatasets={benchmarkDatasets}
            onBack={() => setStep(1)}
            onComplete={(data) => {
              setResults(data);
              goToStep(3, 2);
            }}
          />
        )}

        {step === 3 && results && (
          <ReportStep results={results} onRestart={restart} />
        )}
      </div>
    </DashboardLayout>
  );
}
