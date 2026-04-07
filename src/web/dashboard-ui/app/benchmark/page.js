'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useState, useCallback, useEffect } from 'react';
import axios from 'axios';
import {
  Upload as UploadIcon,
  BarChart3,
  Loader2,
  Trophy,
  FileUp,
  FolderArchive,
  X,
  AlertCircle,
  Zap,
  Target,
  Layers,
  TrendingUp,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  Code2,
  Play,
  FlaskConical,
  Info,
  FileText,
  ArrowRight,
  FileSpreadsheet,
  FileJson,
  File as FileIcon,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const TOOLS = [
  { id: 'integritydesk', name: 'IntegrityDesk', desc: 'Multi-engine fusion (AST + N-gram + Winnowing + Embedding + Token)', color: '#0066cc', gradient: 'from-blue-500 to-blue-600', bgLight: 'bg-blue-50', ring: 'ring-blue-500', engines: ['AST', 'N-gram', 'Winnowing', 'Embedding', 'Token', 'Execution'] },
  { id: 'moss', name: 'MOSS', desc: 'Token-based Jaccard similarity (Stanford)', color: '#7c3aed', gradient: 'from-violet-500 to-violet-600', bgLight: 'bg-violet-50', ring: 'ring-violet-500', engines: ['Token'] },
  { id: 'jplag', name: 'JPlag', desc: 'AST structural comparison (KIT)', color: '#059669', gradient: 'from-emerald-500 to-emerald-600', bgLight: 'bg-emerald-50', ring: 'ring-emerald-500', engines: ['AST'] },
  { id: 'dolos', name: 'Dolos', desc: 'Winnowing fingerprint comparison', color: '#d97706', gradient: 'from-amber-500 to-amber-600', bgLight: 'bg-amber-50', ring: 'ring-amber-500', engines: ['Winnowing'] },
  { id: 'nicad', name: 'NiCad', desc: 'Near-miss clone detector with normalization', color: '#e11d48', gradient: 'from-rose-500 to-rose-600', bgLight: 'bg-rose-50', ring: 'ring-rose-500', engines: ['Normalization'] },
  { id: 'pmd', name: 'PMD CPD', desc: 'Copy/Paste duplicate token sequence detector', color: '#0f766e', gradient: 'from-teal-500 to-teal-600', bgLight: 'bg-teal-50', ring: 'ring-teal-500', engines: ['Duplicate Blocks'] },
  { id: 'sherlock', name: 'Sherlock', desc: 'Line-level textual overlap detector', color: '#4f46e5', gradient: 'from-indigo-500 to-indigo-600', bgLight: 'bg-indigo-50', ring: 'ring-indigo-500', engines: ['Line Overlap'] },
  { id: 'sim', name: 'SIM', desc: 'Dick Grune text similarity tester', color: '#0891b2', gradient: 'from-cyan-500 to-cyan-600', bgLight: 'bg-cyan-50', ring: 'ring-cyan-500', engines: ['Text Similarity'] },
  { id: 'strange', name: 'STRANGE', desc: 'Semantic PDG clone detector', color: '#8b5cf6', gradient: 'from-purple-500 to-purple-600', bgLight: 'bg-purple-50', ring: 'ring-purple-500', engines: ['PDG Analysis'] },
  { id: 'evalforge', name: 'EvalForge', desc: 'Plagiarism detection evaluation framework', color: '#f59e0b', gradient: 'from-orange-500 to-orange-600', bgLight: 'bg-orange-50', ring: 'ring-orange-500', engines: ['Benchmark Runner'] },
  { id: 'gptzero', name: 'GPTZero', desc: 'Open source AI code/text detection', color: '#10b981', gradient: 'from-green-500 to-green-600', bgLight: 'bg-green-50', ring: 'ring-green-500', engines: ['Embedding Analysis'] },
  { id: 'codequiry', name: 'Codequiry', desc: 'Semantic embedding similarity', color: '#dc2626', gradient: 'from-red-500 to-red-600', bgLight: 'bg-red-50', ring: 'ring-red-500', engines: ['Embedding'] },
  { id: 'vendetect', name: 'Vendetect', desc: 'Cross-repository vendored code detection', color: '#ec4899', gradient: 'from-pink-500 to-pink-600', bgLight: 'bg-pink-50', ring: 'ring-pink-500', engines: ['Cross Repo Matching'] },
];

const TEST_CASES = [
  {
    id: 'identical',
    label: 'Identical Files',
    desc: 'Two copies of the same file',
    expected: 0.95,
    codeA: `def calculate_average(data):
    total = sum(data)
    count = len(data)
    return total / count

def find_max(data):
    max_val = data[0]
    for item in data:
        if item > max_val:
            max_val = item
    return max_val`,
    codeB: `def calculate_average(data):
    total = sum(data)
    count = len(data)
    return total / count

def find_max(data):
    max_val = data[0]
    for item in data:
        if item > max_val:
            max_val = item
    return max_val`,
  },
  {
    id: 'renamed',
    label: 'Renamed Variables',
    desc: 'Same logic, different variable/function names',
    expected: 0.80,
    codeA: `def calculate_average(data):
    total = sum(data)
    count = len(data)
    return total / count

def find_max(data):
    max_val = data[0]
    for item in data:
        if item > max_val:
            max_val = item
    return max_val`,
    codeB: `def compute_mean(values):
    total = sum(values)
    count = len(values)
    return total / count

def find_maximum(values):
    max_val = values[0]
    for v in values:
        if v > max_val:
            max_val = v
    return max_val`,
  },
  {
    id: 'reordered',
    label: 'Reordered Functions',
    desc: 'Same functions in different order',
    expected: 0.70,
    codeA: `def calculate_average(data):
    total = sum(data)
    count = len(data)
    return total / count

def find_max(data):
    max_val = data[0]
    for item in data:
        if item > max_val:
            max_val = item
    return max_val

def calculate_sum(data):
    total = 0
    for item in data:
        total += item
    return total`,
    codeB: `def calculate_sum(data):
    total = 0
    for item in data:
        total += item
    return total

def find_max(data):
    max_val = data[0]
    for item in data:
        if item > max_val:
            max_val = item
    return max_val

def calculate_average(data):
    total = sum(data)
    count = len(data)
    return total / count`,
  },
  {
    id: 'similar',
    label: 'Similar Logic',
    desc: 'Same algorithm, different implementation style',
    expected: 0.50,
    codeA: `def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr`,
    codeB: `def sort_array(data):
    n = len(data)
    for i in range(n):
        for j in range(0, n-i-1):
            if data[j] > data[j+1]:
                data[j], data[j+1] = data[j+1], data[j]
    return data`,
  },
  {
    id: 'unrelated',
    label: 'Unrelated Files',
    desc: 'Completely different code, same language',
    expected: 0.10,
    codeA: `import numpy as np

def calculate_portfolio_returns(weights, returns_matrix):
    weighted_returns = np.dot(weights, returns_matrix)
    return weighted_returns

def sharpe_ratio(returns, risk_free_rate=0.02):
    excess_returns = returns - risk_free_rate
    return np.mean(excess_returns) / np.std(excess_returns)`,
    codeB: `from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    user = User(username=data['username'], email=data['email'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'id': user.id}), 201`,
  },
];

const DATASETS = [
  {
    id: 'basic-clone',
    name: 'Basic Clone Detection',
    desc: '5 test cases: identical, renamed, reordered, similar, and unrelated code pairs',
    icon: '🧪',
    color: 'blue',
    cases: TEST_CASES,
  },
  {
    id: 'obfuscation',
    name: 'Obfuscation Resistance',
    desc: 'Test how well tools detect plagiarism through variable renaming, reordering, and comment changes',
    icon: '🔍',
    color: 'violet',
    cases: [
      {
        id: 'obf-rename',
        label: 'Variable Renaming',
        desc: 'All identifiers renamed, same logic',
        expected: 0.80,
        codeA: `def calculate_average(data):
    total = sum(data)
    count = len(data)
    return total / count

def find_max(data):
    max_val = data[0]
    for item in data:
        if item > max_val:
            max_val = item
    return max_val

def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr`,
        codeB: `def compute_mean(values):
    total = sum(values)
    cnt = len(values)
    return total / cnt

def find_maximum(vals):
    mx = vals[0]
    for v in vals:
        if v > mx:
            mx = v
    return mx

def sort_list(lst):
    size = len(lst)
    for i in range(size):
        for j in range(0, size-i-1):
            if lst[j] > lst[j+1]:
                lst[j], lst[j+1] = lst[j+1], lst[j]
    return lst`,
      },
      {
        id: 'obf-reorder',
        label: 'Function Reordering',
        desc: 'Same functions in different order',
        expected: 0.70,
        codeA: `def factorial(n):
    if n <= 1:
            return 1
    return n * factorial(n-1)

def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n+1):
        a, b = b, a+b
    return b

def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5)+1):
        if n % i == 0:
            return False
    return True`,
        codeB: `def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5)+1):
        if n % i == 0:
            return False
    return True

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)

def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n+1):
        a, b = b, a+b
    return b`,
      },
      {
        id: 'obf-comments',
        label: 'Comment/Whitespace Changes',
        desc: 'Added comments, blank lines, and whitespace changes',
        expected: 0.90,
        codeA: `def binary_search(arr, target):
    left = 0
    right = len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1`,
        codeB: `# Binary search implementation
# Returns index of target or -1 if not found
def binary_search(arr, target):
    # Initialize search boundaries
    left = 0
    right = len(arr) - 1

    # Continue while search space exists
    while left <= right:
        # Calculate midpoint
        mid = (left + right) // 2

        # Check if we found the target
        if arr[mid] == target:
            return mid
        # Target is in the right half
        elif arr[mid] < target:
            left = mid + 1
        # Target is in the left half
        else:
            right = mid - 1

    # Target not found
    return -1`,
      },
    ],
  },
  {
    id: 'multi-file',
    name: 'Multi-File Class',
    desc: 'Simulated class of 6 student submissions with varying similarity levels',
    icon: '👥',
    color: 'emerald',
    cases: [
      {
        id: 'class-1-2',
        label: 'Student 1 vs Student 2',
        desc: 'Direct copy with renamed variables',
        expected: 0.85,
        codeA: `class Stack:
    def __init__(self):
        self.items = []
    def push(self, item):
        self.items.append(item)
    def pop(self):
        return self.items.pop()
    def is_empty(self):
        return len(self.items) == 0
    def peek(self):
        return self.items[-1]`,
        codeB: `class Stack:
    def __init__(self):
        self.elements = []
    def push(self, element):
        self.elements.append(element)
    def pop(self):
        return self.elements.pop()
    def is_empty(self):
        return len(self.elements) == 0
    def peek(self):
        return self.elements[-1]`,
      },
      {
        id: 'class-3-4',
        label: 'Student 3 vs Student 4',
        desc: 'Similar algorithm, different style',
        expected: 0.55,
        codeA: `def linear_search(arr, target):
    for i in range(len(arr)):
        if arr[i] == target:
            return i
    return -1`,
        codeB: `def search_list(data, key):
    index = 0
    while index < len(data):
        if data[index] == key:
            return index
        index += 1
    return -1`,
      },
      {
        id: 'class-5-6',
        label: 'Student 5 vs Student 6',
        desc: 'Completely different implementations',
        expected: 0.15,
        codeA: `def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)

def merge(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result`,
        codeB: `def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)`,
      },
    ],
  },
  {
    id: 'java-clone',
    name: 'Java Clone Detection',
    desc: 'Java code pairs testing clone detection across languages',
    icon: '☕',
    color: 'amber',
    cases: [
      {
        id: 'java-identical',
        label: 'Identical Java',
        desc: 'Two copies of the same Java class',
        expected: 0.95,
        codeA: `public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
    public int subtract(int a, int b) {
        return a - b;
    }
    public int multiply(int a, int b) {
        return a * b;
    }
    public double divide(int a, int b) {
        if (b == 0) throw new ArithmeticException();
        return (double) a / b;
    }
}`,
        codeB: `public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
    public int subtract(int a, int b) {
        return a - b;
    }
    public int multiply(int a, int b) {
        return a * b;
    }
    public double divide(int a, int b) {
        if (b == 0) throw new ArithmeticException();
        return (double) a / b;
    }
}`,
      },
      {
        id: 'java-renamed',
        label: 'Renamed Java Methods',
        desc: 'Same logic with renamed methods and variables',
        expected: 0.75,
        codeA: `public class LinkedList {
    private Node head;
    public void insert(int data) {
        Node newNode = new Node(data);
        newNode.next = head;
        head = newNode;
    }
    public boolean contains(int data) {
        Node current = head;
        while (current != null) {
            if (current.data == data) return true;
            current = current.next;
        }
        return false;
    }
}`,
        codeB: `public class SingleList {
    private Node first;
    public void add(int value) {
        Node node = new Node(value);
        node.next = first;
        first = node;
    }
    public boolean hasValue(int value) {
        Node temp = first;
        while (temp != null) {
            if (temp.data == value) return true;
            temp = temp.next;
        }
        return false;
    }
}`,
      },
    ],
  },
];

export default function BenchmarkPage() {
  const [tab, setTab] = useState('quick');
  const [mode, setMode] = useState('individual');
  const [files, setFiles] = useState([]);
  const [selectedTools, setSelectedTools] = useState([]); // Start with no tools selected
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState('');
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');
  const [expandedPairs, setExpandedPairs] = useState({});
  const [selectedDataset, setSelectedDataset] = useState('basic-clone');
  const [selectedTestCase, setSelectedTestCase] = useState(null);
  const [benchmarkDatasets, setBenchmarkDatasets] = useState([]);

  useEffect(() => {
    axios.get(`${API}/api/benchmark-datasets`).then((res) => {
      if (res.data?.datasets) {
        setBenchmarkDatasets(res.data.datasets);
      }
    }).catch(() => {});
  }, []);

  const activeDataset = DATASETS.find(d => d.id === selectedDataset) || DATASETS[0];
  const activeCases = activeDataset?.cases || [];

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setFiles(Array.from(e.dataTransfer.files));
  }, []);

  const toggleTool = (id) => {
    setSelectedTools((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
  };

  const selectAll = () => setSelectedTools(TOOLS.map(t => t.id));
  const deselectAll = () => setSelectedTools([]);

  const runQuickTest = async (testCase) => {
    if (selectedTools.length === 0) {
      setError('Please select at least one detection tool (Step 1)');
      return;
    }

    setSelectedTestCase(testCase.id);
    setError('');
    setRunning(true);
    setResults(null);
    setProgress(`Running "${testCase.label}" across ${selectedTools.length} tool(s)...`);

    const blobA = new Blob([testCase.codeA], { type: 'text/plain' });
    const blobB = new Blob([testCase.codeB], { type: 'text/plain' });
    const fileA = new File([blobA], `${testCase.id}_a.py`, { type: 'text/plain' });
    const fileB = new File([blobB], `${testCase.id}_b.py`, { type: 'text/plain' });

    const formData = new FormData();
    formData.append('files', fileA);
    formData.append('files', fileB);
    selectedTools.forEach((t) => formData.append('tools', t));

    try {
      const res = await axios.post(`${API}/api/benchmark`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResults({ ...res.data, testCase });
    } catch (err) {
      setError(err.response?.data?.error || 'Benchmark failed');
    }
    setRunning(false);
    setProgress('');
  };

  const runUploadBenchmark = async () => {
    if (selectedTools.length === 0) {
      setError('Please select at least one detection tool (Step 1)');
      return;
    }
    if (mode === 'individual' && files.length < 2) {
      setError('Upload at least 2 files (Step 3)');
      return;
    }
    if (mode === 'zip' && !files.length) {
      setError('Select a ZIP file (Step 3)');
      return;
    }

    setError('');
    setRunning(true);
    setResults(null);
    setProgress('Uploading files...');

    const formData = new FormData();
    if (mode === 'individual') {
      files.forEach((f) => formData.append('files', f));
    }
    selectedTools.forEach((t) => formData.append('tools', t));

    try {
      setProgress('Running analysis across all tools...');
      const res = await axios.post(`${API}/api/benchmark`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setProgress('Compiling results...');
      setResults(res.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Benchmark failed');
    }
    setRunning(false);
    setProgress('');
  };

  // Export functions
  const exportToJSON = () => {
    if (!results) return;
    const dataStr = JSON.stringify(results, null, 2);
    const dataUri = URL.createObjectURL(new Blob([dataStr], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = dataUri;
    link.download = 'benchmark-results.json';
    link.click();
  };

  const exportToCSV = () => {
    if (!results) return;
    const { pair_results, tool_scores } = results;
    const activeTools = Object.keys(tool_scores);
    
    let csv = 'Pair,File A,File B,' + activeTools.map(t => TOOLS.find(tool => tool.id === t)?.name || t).join(',') + '\n';
    
    pair_results.forEach(pair => {
      const scores = activeTools.map(t => {
        const tr = pair.tool_results?.find(r => r.tool === t);
        return tr ? (tr.score * 100).toFixed(1) + '%' : 'N/A';
      });
      csv += `"${pair.label}","${pair.file_a}","${pair.file_b}",${scores.join(',')}\n`;
    });

    const dataUri = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const link = document.createElement('a');
    link.href = dataUri;
    link.download = 'benchmark-results.csv';
    link.click();
  };

  const exportToPDF = () => {
    // Open print dialog for PDF export
    window.print();
  };

  return (
    <DashboardLayout>
      <div className="p-4 lg:p-6">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
              <FlaskConical size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Benchmark Suite</h1>
              <p className="text-slate-500 mt-0.5">
                Test and compare plagiarism detection tools with known test cases or your own files.
              </p>
            </div>
          </div>
        </div>

        {/* Step Indicator */}
        <div className="mb-6 bg-white rounded-2xl border border-slate-200 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${selectedTools.length > 0 ? 'bg-violet-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                1
              </div>
              <div>
                <p className="font-semibold text-slate-900">Choose Tools</p>
                <p className="text-xs text-slate-500">{selectedTools.length} selected</p>
              </div>
            </div>
            <div className="flex-1 mx-4 h-0.5 bg-slate-100" />
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${selectedDataset ? 'bg-violet-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                2
              </div>
              <div>
                <p className="font-semibold text-slate-900">Choose Dataset</p>
                <p className="text-xs text-slate-500">{activeDataset?.name}</p>
              </div>
            </div>
            <div className="flex-1 mx-4 h-0.5 bg-slate-100" />
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${running ? 'bg-violet-600 text-white animate-pulse' : 'bg-slate-100 text-slate-500'}`}>
                3
              </div>
              <div>
                <p className="font-semibold text-slate-900">Run & Export</p>
                <p className="text-xs text-slate-500">{results ? 'Results ready' : 'Start analysis'}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => { setTab('quick'); setResults(null); setSelectedTestCase(null); }}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              tab === 'quick'
                ? 'bg-violet-600 text-white shadow-lg shadow-violet-500/25'
                : 'bg-white border border-slate-200 text-slate-600 hover:border-slate-300'
            }`}
          >
            <Play size={15} />
            Quick Test Cases
          </button>
          <button
            onClick={() => { setTab('upload'); setResults(null); setSelectedTestCase(null); }}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
              tab === 'upload'
                ? 'bg-violet-600 text-white shadow-lg shadow-violet-500/25'
                : 'bg-white border border-slate-200 text-slate-600 hover:border-slate-300'
            }`}
          >
            <UploadIcon size={15} />
            Upload Files
          </button>
        </div>

        {/* Step 1: Tool Selection - Shared */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
          <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-slate-900">Step 1: Select Detection Tools</h2>
              <p className="text-sm text-slate-500 mt-0.5">
                {selectedTools.length === 0 ? 'No tools selected — choose at least one to proceed' : `${selectedTools.length} of ${TOOLS.length} tools selected`}
              </p>
            </div>
            <div className="flex gap-2">
              <button onClick={selectAll} className="text-xs font-medium text-blue-600 hover:text-blue-700 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors">
                Select All
              </button>
              <button onClick={deselectAll} className="text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">
                Clear
              </button>
            </div>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {TOOLS.map((tool) => {
                const isSelected = selectedTools.includes(tool.id);
                return (
                  <button
                    key={tool.id}
                    onClick={() => toggleTool(tool.id)}
                    className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 ${
                      isSelected
                        ? `border-transparent ring-2 ${tool.ring} ring-offset-2`
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    {isSelected && (
                      <div className="absolute top-2 right-2">
                        <CheckCircle2 size={16} className={tool.color.replace('500', '600')} />
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
        </div>

        {/* Step 2 & 3: Dataset Selection and Run */}
        {tab === 'quick' && (
          <div className="space-y-6 mb-6">
            {/* Dataset Selector (Step 2) */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-5 border-b border-slate-100">
                <h2 className="font-semibold text-slate-900">Step 2: Choose Dataset</h2>
                <p className="text-sm text-slate-500 mt-0.5">
                  Select a test dataset to run against your chosen tools.
                </p>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {DATASETS.map((ds) => {
                    const isActive = selectedDataset === ds.id;
                    return (
                      <button
                        key={ds.id}
                        onClick={() => { setSelectedDataset(ds.id); setSelectedTestCase(null); setResults(null); }}
                        className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 ${
                          isActive
                            ? 'border-violet-400 bg-violet-50 ring-2 ring-violet-500/20'
                            : 'border-slate-200 hover:border-slate-300 bg-white hover:shadow-md'
                        }`}
                      >
                        {isActive && (
                          <div className="absolute top-2 right-2">
                            <CheckCircle2 size={14} className="text-violet-600" />
                          </div>
                        )}
                        <div className="text-xl mb-2">{ds.icon}</div>
                        <div className="font-semibold text-sm text-slate-900">{ds.name}</div>
                        <div className="text-xs text-slate-500 mt-1 line-clamp-2">{ds.desc}</div>
                        <div className="text-xs font-medium text-violet-600 mt-2">{ds.cases.length} test cases</div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Test Cases (Step 3 - Run) */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-6 py-5 border-b border-slate-100">
                <h2 className="font-semibold text-slate-900">Step 3: Run Test</h2>
                <p className="text-sm text-slate-500 mt-0.5">
                  Click any test case to run it across all selected tools.
                </p>
              </div>
              <div className="p-6">
                {selectedTools.length === 0 ? (
                  <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-100 rounded-xl">
                    <AlertCircle size={18} className="text-amber-500 shrink-0" />
                    <p className="text-sm text-amber-700">Please select at least one detection tool above before running tests.</p>
                  </div>
                ) : (
                  <div className="grid md:grid-cols-5 gap-3">
                    {activeCases.map((tc) => (
                      <button
                        key={tc.id}
                        onClick={() => runQuickTest(tc)}
                        disabled={running}
                        className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed ${
                          selectedTestCase === tc.id && running
                            ? 'border-violet-300 bg-violet-50 ring-2 ring-violet-500 ring-offset-2'
                            : 'border-slate-200 hover:border-violet-300 hover:shadow-md bg-white'
                        }`}
                      >
                        {selectedTestCase === tc.id && running && (
                          <div className="absolute top-2 right-2">
                            <Loader2 size={14} className="text-violet-600 animate-spin" />
                          </div>
                        )}
                        <div className="flex items-center gap-2 mb-2">
                          <div className={`w-2 h-2 rounded-full ${
                            tc.expected >= 0.9 ? 'bg-red-500' : tc.expected >= 0.7 ? 'bg-amber-500' : tc.expected >= 0.4 ? 'bg-yellow-500' : 'bg-emerald-500'
                          }`} />
                          <span className="text-xs font-semibold text-slate-500">Expected ~{(tc.expected * 100).toFixed(0)}%</span>
                        </div>
                        <div className="font-semibold text-sm text-slate-900">{tc.label}</div>
                        <div className="text-xs text-slate-400 mt-1">{tc.desc}</div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Upload Section (Step 2 & 3) */}
        {tab === 'upload' && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
            <div className="px-6 py-5 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Step 2 & 3: Upload and Run</h2>
              <p className="text-sm text-slate-500 mt-0.5">
                Upload your files and run the analysis across all selected tools.
              </p>
            </div>
            <div className="p-6">
              {/* Mode Toggle */}
              <div className="flex gap-2 mb-5">
                <button
                  onClick={() => setMode('individual')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                    mode === 'individual'
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
                      : 'bg-white border border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <FileUp size={15} />
                  Individual Files
                </button>
                <button
                  onClick={() => setMode('zip')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                    mode === 'zip'
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
                      : 'bg-white border border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <FolderArchive size={15} />
                  ZIP Archive
                </button>
              </div>

              {/* Drop Zone */}
              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className="border-2 border-dashed border-slate-200 rounded-xl p-10 text-center hover:border-blue-400 hover:bg-blue-50/30 transition-all duration-200 cursor-pointer group"
                onClick={() => document.getElementById('benchFileInput').click()}
              >
                <div className="w-14 h-14 rounded-2xl bg-slate-50 flex items-center justify-center mx-auto mb-4 group-hover:bg-blue-50 transition-colors">
                  <UploadIcon size={24} className="text-slate-400 group-hover:text-blue-500 transition-colors" />
                </div>
                <p className="text-sm font-semibold text-slate-700 mb-1">
                  {mode === 'individual' ? 'Drop files here or click to browse' : 'Drop ZIP file here or click to browse'}
                </p>
                <p className="text-xs text-slate-400">
                  {mode === 'individual' ? 'Python, Java, C/C++, JavaScript, Rust, Go, and 20+ languages' : 'All code files within the archive will be analyzed'}
                </p>
                <input id="benchFileInput" type="file" multiple accept=".py,.java,.c,.cpp,.h,.js,.ts,.go,.rs,.rb,.php,.cs,.kt,.swift" className="hidden" onChange={(e) => setFiles(Array.from(e.target.files))} />
              </div>

              {/* File List */}
              {files.length > 0 && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      {files.length} files selected
                    </span>
                    <button onClick={() => setFiles([])} className="text-xs text-slate-400 hover:text-red-500 transition-colors">Clear all</button>
                  </div>
                  <div className="space-y-1.5 max-h-36 overflow-y-auto scrollbar-thin pr-1">
                    {files.map((f, i) => (
                      <div key={i} className="flex items-center justify-between px-3 py-2.5 bg-slate-50 rounded-lg text-sm group/file">
                        <div className="flex items-center gap-2 min-w-0 flex-1">
                          <div className="w-7 h-7 rounded-md bg-emerald-50 flex items-center justify-center shrink-0">
                            <FileUp size={12} className="text-emerald-600" />
                          </div>
                          <span className="font-medium text-slate-700 truncate">{f.name}</span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0 ml-2">
                          <span className="text-xs text-slate-400">{(f.size / 1024).toFixed(1)} KB</span>
                          <button onClick={() => setFiles(files.filter((_, j) => j !== i))} className="opacity-0 group-hover/file:opacity-100 text-slate-300 hover:text-red-500 transition-all">
                            <X size={14} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="mt-4 flex items-start gap-3 p-4 bg-red-50 border border-red-100 rounded-xl">
                  <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              {/* Progress */}
              {running && (
                <div className="mt-4 flex items-center gap-3 p-4 bg-blue-50 border border-blue-100 rounded-xl">
                  <Loader2 size={18} className="text-blue-600 animate-spin shrink-0" />
                  <p className="text-sm text-blue-700 font-medium">{progress}</p>
                </div>
              )}

              {/* Submit */}
              <button
                onClick={runUploadBenchmark}
                disabled={running || selectedTools.length === 0 || (mode === 'individual' && files.length < 2)}
                className="w-full mt-5 py-3.5 bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-700 hover:to-blue-700 disabled:from-slate-300 disabled:to-slate-200 text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-violet-500/25 hover:shadow-xl hover:shadow-violet-500/30 disabled:shadow-none"
              >
                {running ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Running All Tools...
                  </>
                ) : (
                  <>
                    <BarChart3 size={18} />
                    Run {selectedTools.length} Tool{selectedTools.length !== 1 ? 's' : ''} on {files.length} File{files.length !== 1 ? 's' : ''}
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Results with Export Options */}
        {results && (
          <div className="space-y-6">
            {/* Export Buttons */}
            <div className="flex flex-wrap gap-3">
              <button
                onClick={exportToJSON}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-xl font-medium transition-colors"
              >
                <FileJson size={16} />
                Export JSON
              </button>
              <button
                onClick={exportToCSV}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition-colors"
              >
                <FileSpreadsheet size={16} />
                Export CSV
              </button>
              <button
                onClick={exportToPDF}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl font-medium transition-colors"
              >
                <File size={16} />
                Export PDF
              </button>
            </div>

            {/* Results Component */}
            <BenchmarkResults results={results} expandedPairs={expandedPairs} setExpandedPairs={setExpandedPairs} />
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function BenchmarkResults({ results, expandedPairs, setExpandedPairs }) {
  const { tool_scores, pair_results, summary, testCase } = results;
  const activeTools = Object.keys(tool_scores);

  const chartData = pair_results.map((pair) => {
    const d = { pair: pair.label };
    activeTools.forEach((t) => {
      const tr = pair.tool_results?.find((r) => r.tool === t);
      d[t] = tr ? Math.round(tr.score * 1000) / 10 : 0;
    });
    return d;
  });

  const radarData = activeTools.map((tool) => {
    const d = { tool: TOOLS.find(t => t.id === tool)?.name || tool };
    pair_results.forEach((pair) => {
      const tr = pair.tool_results?.find((r) => r.tool === tool);
      d[pair.label] = tr ? Math.round(tr.score * 1000) / 10 : 0;
    });
    return d;
  });

  const TOOL_COLORS = {
    integritydesk: '#0066cc',
    moss: '#7c3aed',
    jplag: '#059669',
    dolos: '#d97706',
    codequiry: '#dc2626',
  };

  const togglePair = (idx) => {
    setExpandedPairs((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <div className="space-y-6">
      {/* Test Case Info */}
      {testCase && (
        <div className="bg-gradient-to-r from-violet-50 to-blue-50 border border-violet-200 rounded-2xl p-5 flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center shrink-0">
              <FlaskConical size={20} className="text-violet-600" />
            </div>
            <div>
              <p className="font-semibold text-violet-900">Test Case: {testCase.label}</p>
              <p className="text-sm text-violet-700 mt-0.5">
                {testCase.desc} — Expected similarity: ~{(testCase.expected * 100).toFixed(0)}%
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-violet-600 bg-violet-100 px-3 py-1.5 rounded-lg">
              Expected: {(testCase.expected * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
              <Layers size={18} className="text-blue-600" />
            </div>
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Tools Run</span>
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.tools_compared || 0}</div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center">
              <Target size={18} className="text-emerald-600" />
            </div>
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Pairs Tested</span>
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.pairs_tested || 0}</div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
              <TrendingUp size={18} className="text-blue-600" />
            </div>
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">IntegrityDesk Avg</span>
          </div>
          <div className="text-2xl font-bold text-blue-600">{summary?.accuracy ? (summary.accuracy.integritydesk * 100).toFixed(1) : 0}%</div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-slate-50 flex items-center justify-center">
              <Trophy size={18} className="text-slate-600" />
            </div>
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Best Competitor</span>
          </div>
          <div className="text-2xl font-bold text-slate-700">{summary?.accuracy ? (summary.accuracy.best_competitor * 100).toFixed(1) : 0}%</div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Bar Chart */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-5 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900">Score Comparison</h2>
            <p className="text-sm text-slate-500 mt-0.5">Similarity scores per file pair</p>
          </div>
          <div className="p-6">
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="pair" tick={{ fontSize: 11, fill: '#64748b' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} domain={[0, 100]} />
                  <Tooltip formatter={(value) => `${value.toFixed(1)}%`} contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                  <Legend wrapperStyle={{ fontSize: '12px' }} />
                  {activeTools.map((tool) => (
                    <Bar key={tool} dataKey={tool} fill={TOOL_COLORS[tool] || '#94a3b8'} radius={[4, 4, 0, 0]} name={TOOLS.find(t => t.id === tool)?.name || tool} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Radar Chart */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-5 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900">Tool Radar</h2>
            <p className="text-sm text-slate-500 mt-0.5">Multi-dimensional tool comparison</p>
          </div>
          <div className="p-6">
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="tool" tick={{ fontSize: 11, fill: '#64748b' }} />
                  <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
                  <Legend wrapperStyle={{ fontSize: '12px' }} />
                  {pair_results.map((pair, i) => (
                    <Radar
                      key={pair.label}
                      name={pair.label}
                      dataKey={pair.label}
                      stroke={TOOL_COLORS.integritydesk}
                      fill={TOOL_COLORS.integritydesk}
                      fillOpacity={0.1 + i * 0.1}
                    />
                  ))}
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>

      {/* Detailed Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900">Detailed Pair Results</h2>
          <p className="text-sm text-slate-500 mt-0.5">Click any pair to see individual tool scores</p>
        </div>

        {/* Table Header */}
        <div className="hidden lg:grid grid-cols-12 gap-4 px-6 py-3 bg-slate-50/80 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
          <div className="col-span-3">File Pair</div>
          {activeTools.map((tool) => (
            <div key={tool} className="col-span-2 text-center flex items-center justify-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: TOOL_COLORS[tool] }} />
              {TOOLS.find(t => t.id === tool)?.name || tool}
            </div>
          ))}
          <div className="col-span-1 text-center">Max</div>
          <div className="col-span-1 text-center">Min</div>
          <div className="col-span-1 text-center">Spread</div>
        </div>

        {/* Rows */}
        <div className="divide-y divide-slate-50">
          {pair_results.map((pair, idx) => {
            const scores = activeTools.map((t) => {
              const tr = pair.tool_results?.find((r) => r.tool === t);
              return tr ? tr.score : null;
            });
            const validScores = scores.filter((s) => s !== null);
            const maxScore = validScores.length ? Math.max(...validScores) : 0;
            const minScore = validScores.length ? Math.min(...validScores) : 0;
            const spread = maxScore - minScore;
            const isExpanded = expandedPairs[idx];

            return (
              <div key={idx}>
                <button
                  onClick={() => togglePair(idx)}
                  className="w-full lg:grid lg:grid-cols-12 lg:gap-4 px-6 py-4 hover:bg-slate-50/50 transition-colors text-left flex flex-col lg:flex-row lg:items-center"
                >
                  <div className="col-span-3 flex items-center gap-3 mb-2 lg:mb-0">
                    <div className={`w-2 h-8 rounded-full ${maxScore >= 0.9 ? 'bg-red-500' : maxScore >= 0.75 ? 'bg-amber-500' : maxScore >= 0.5 ? 'bg-yellow-500' : 'bg-emerald-500'}`} />
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{pair.label}</div>
                      <div className="text-xs text-slate-400">{pair.file_a} vs {pair.file_b}</div>
                    </div>
                    {isExpanded ? <ChevronUp size={14} className="text-slate-400 ml-auto lg:ml-0" /> : <ChevronDown size={14} className="text-slate-400 ml-auto lg:ml-0" />}
                  </div>
                  {activeTools.map((tool, ti) => {
                    const score = scores[ti];
                    return (
                      <div key={tool} className="col-span-2 text-center py-1 lg:py-0">
                        {score !== null ? (
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold ${tool === 'integritydesk' ? 'bg-blue-50 text-blue-700' : 'bg-slate-50 text-slate-600'}`}>
                            {(score * 100).toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-xs text-slate-300">N/A</span>
                        )}
                      </div>
                    );
                  })}
                  <div className="hidden lg:flex col-span-1 items-center justify-center">
                    <span className="text-xs font-bold text-red-600">{(maxScore * 100).toFixed(0)}%</span>
                  </div>
                  <div className="hidden lg:flex col-span-1 items-center justify-center">
                    <span className="text-xs font-bold text-emerald-600">{(minScore * 100).toFixed(0)}%</span>
                  </div>
                  <div className="hidden lg:flex col-span-1 items-center justify-center">
                    <span className={`text-xs font-bold ${spread >= 0.3 ? 'text-red-600' : 'text-emerald-600'}`}>
                      {(spread * 100).toFixed(0)}%
                    </span>
                  </div>
                </button>

                {isExpanded && (
                  <div className="px-6 pb-5 bg-slate-50/50">
                    <div className="grid md:grid-cols-2 gap-4 mt-3">
                      {pair.tool_results?.map((tr) => {
                        const toolInfo = TOOLS.find(t => t.id === tr.tool);
                        if (!toolInfo) return null;
                        const scorePct = (tr.score * 100).toFixed(1);
                        return (
                          <div key={tr.tool} className="bg-white rounded-xl border border-slate-200 p-4">
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center gap-2">
                                <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${toolInfo.gradient} flex items-center justify-center`}>
                                  <Zap size={13} className="text-white" />
                                </div>
                                <span className="text-sm font-semibold text-slate-900">{toolInfo.name}</span>
                              </div>
                              <span className={`text-lg font-bold ${tr.tool === 'integritydesk' ? 'text-blue-600' : 'text-slate-700'}`}>
                                {scorePct}%
                              </span>
                            </div>
                            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                              <div
                                className="h-full rounded-full transition-all duration-500"
                                style={{ width: `${tr.score * 100}%`, background: `linear-gradient(90deg, ${toolInfo.color}, ${toolInfo.color}dd)` }}
                              />
                            </div>
                            <div className="flex items-center justify-between mt-2">
                              <span className="text-xs text-slate-400">
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
    </div>
  );
}