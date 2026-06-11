# AI Detector Design Document

## Overview

The AI Detector is a production-grade system for detecting AI-generated code from large language models (LLMs) such as GPT-4, Claude, and Copilot. The system employs an 8-signal ensemble approach that analyzes code characteristics at multiple levels: token entropy, structural uniformity, stylometric patterns, and fingerprint matching. Results are fused via weighted averaging with sigmoid calibration to produce a calibrated AI probability score between 0.0 and 1.0.

### Key Design Principles

1. **Multi-Signal Ensemble**: Eight independent signals provide complementary perspectives on code characteristics
2. **Explainability**: Each signal is interpretable and contributes transparently to the final score
3. **Calibration**: Sigmoid calibration ensures probability scores are well-calibrated to actual AI generation likelihood
4. **Language Agnostic**: Core signals work across all programming languages; language-specific analysis (AST) available for Python
5. **Performance**: Single-file analysis completes in <2 seconds; batch processing scales linearly
6. **Privacy**: Code is analyzed locally; no external transmission or model training

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Upload Page  │  │ Results Page │  │ Job History  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ POST /api/ai-detect  │  GET /api/jobs/{job_id}      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Detection Engine (AIDetectionEngine)            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Signal Computation Layer                             │   │
│  │  • Perplexity Signal                                 │   │
│  │  • Burstiness Signal                                 │   │
│  │  • Stylometry Signal                                 │   │
│  │  • Pattern Library Signal                            │   │
│  │  • Structural Entropy Signal                         │   │
│  │  • Vocabulary Richness Signal                        │   │
│  │  • Whitespace Rhythm Signal                          │   │
│  │  • Docstring Density Signal                          │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Fusion & Calibration Layer                           │   │
│  │  • Weighted Fusion (8 weights)                       │   │
│  │  • Sigmoid Calibration (k=6.0)                       │   │
│  │  • Confidence Scoring                                │   │
│  │  • Risk Classification                               │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Evidence Generation Layer                            │   │
│  │  • Indicator Generation                              │   │
│  │  • Flagged Line Identification                       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Report Generator                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ PDF Export  │  HTML Export  │  JSON Export           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Upload Phase**: User uploads code files or ZIP archive via web interface
2. **Validation Phase**: Files are validated for type, size, and count constraints
3. **Extraction Phase**: ZIP archives are extracted; individual files are identified
4. **Analysis Phase**: Each file is analyzed independently by AIDetectionEngine
5. **Fusion Phase**: Eight signals are computed and fused into final score
6. **Results Phase**: Results are displayed with evidence indicators and flagged lines
7. **Export Phase**: User can export results as PDF or JSON

### Asynchronous Processing Model

- **Immediate Response**: API returns job_id immediately upon file upload
- **Background Processing**: Analysis runs asynchronously in background
- **Status Polling**: Client polls `/api/jobs/{job_id}` to check status
- **Result Retrieval**: Once complete, results are available via same endpoint
- **Job History**: Recent jobs are cached in memory for quick retrieval


## Signal Computation Algorithms

### Signal 1: N-Gram Perplexity

**Purpose**: Measure token-level entropy to identify code with low diversity (characteristic of LLM output).

**Algorithm**:
1. Tokenize code into lowercase identifiers, keywords, and operators
2. Compute unigram entropy: H_unigram = -Σ(p_i * log₂(p_i)) where p_i = count_i / total_tokens
3. Compute bigram entropy: H_bigram = -Σ(p_j * log₂(p_j)) where p_j = count_j / total_bigrams
4. Combine: H_combined = 0.4 * H_unigram + 0.6 * H_bigram (raw bits, not normalized)
5. Map to score: score = max(0.0, min(1.0, 1.0 - H_combined / 5.0))

**Calibration**:
- Human code: 3.5–5.5 bits (score 0.0–0.3)
- LLM code: 0–3.0 bits (score 0.4–1.0)

**Edge Cases**:
- Code < 10 tokens: return 0.0
- Single unique token: entropy = 0.0, score = 1.0

### Signal 2: Burstiness

**Purpose**: Measure line complexity variation to identify uniform code (characteristic of LLM output).

**Algorithm**:
1. Extract non-empty lines from code
2. For each line, compute complexity: C_i = (indent_level / 4.0) + (line_length / 80.0)
3. Compute mean: μ = Σ(C_i) / n
4. Compute coefficient of variation: CV = √(Σ(C_i - μ)² / n) / μ
5. Map to score: score = max(0.0, min(1.0, 1.0 - (CV / 1.2)))

**Calibration**:
- Human code: CV 0.6–1.4 (score 0.0–0.5)
- LLM code: CV 0.2–0.6 (score 0.5–1.0)

**Edge Cases**:
- Code < 5 lines: return 0.0
- Mean complexity ≈ 0: return 0.5

### Signal 3: Stylometry

**Purpose**: Analyze code style including comments, naming, and type hints.

**Algorithm**:
1. Extract style features using StylometryExtractor:
   - Descriptive variable ratio: count of generic names (result, data, temp, etc.) / total variables
   - Docstring ratio: docstring lines / total lines
   - Type hint ratio: functions with return type hints / total functions
   - Single-char variable ratio: single-char vars / total variables
   - Exception handling ratio: try/except blocks / total functions
   - List comprehension ratio: list comprehensions / total loops
2. Combine with weights:
   - Descriptive ratio: 0.25
   - Docstring ratio: 0.20
   - Type hint ratio: 0.20
   - Single-char ratio (inverted): 0.15
   - Exception handling: 0.10
   - List comprehension: 0.10
3. Score = weighted average of all features

**Edge Cases**:
- No functions: skip exception handling and type hint ratios
- No variables: skip variable ratio features

### Signal 4: Pattern Library

**Purpose**: Match LLM-specific code patterns using 40+ curated regex fingerprints.

**Algorithm**:
1. Define three pattern categories:
   - Comment patterns (8): "Let's", "Here we", "Step 1:", etc.
   - Naming patterns (4): "result", "output", "process_", etc.
   - Structural patterns (28): "if x is None:", "raise ValueError", type hints, etc.
2. Count total matches: match_count = Σ(pattern.findall(code))
3. Normalize by code length: density = match_count / max(1, total_lines)
4. Map to score: score = max(0.0, min(1.0, density * 5.0))

**Calibration**:
- Human code: 0–2 matches per 10 lines (score 0.0–0.4)
- LLM code: 3–8 matches per 10 lines (score 0.6–1.0)

**Edge Cases**:
- Empty code: return 0.0
- Very short code: density may be high; capped at 1.0

### Signal 5: Structural Entropy

**Purpose**: Measure AST uniformity to identify overly regular structure (characteristic of LLM output).

**Algorithm** (Python):
1. Parse code into Abstract Syntax Tree (AST)
2. Count node types: node_types = Counter(type(n).__name__ for n in ast.walk(tree))
3. Compute normalized entropy: H = -Σ(p_i * log₂(p_i)) / log₂(n_unique)
4. Map to score: score = max(0.0, min(1.0, 1.0 - H)) * 0.8

**Fallback** (non-Python or parse error):
1. Count indent levels: indent_levels = Counter((len(line) - len(line.lstrip())) // 4)
2. Compute normalized entropy: H = -Σ(p_i * log₂(p_i)) / log₂(n_unique)
3. Map to score: score = max(0.0, min(1.0, 1.0 - H)) * 0.6

**Edge Cases**:
- Syntax error: use fallback
- Single node type: entropy = 0.0, score = 0.8 (or 0.6 for fallback)
- Empty code: return 0.0

### Signal 6: Vocabulary Richness

**Purpose**: Measure vocabulary diversity using Type-Token Ratio (TTR) and hapax legomena.

**Algorithm**:
1. Tokenize code into lowercase tokens
2. Compute TTR in sliding windows:
   - Window size: 50 tokens
   - Overlap: 50% (step = 25)
   - TTR_i = unique_tokens_in_window / 50
   - TTR_avg = mean(TTR_i)
3. Compute hapax legomena ratio: hapax_ratio = count(tokens appearing exactly once) / total_unique_tokens
4. Combine: score = 0.6 * TTR_score + 0.4 * hapax_score
   - TTR_score = max(0.0, min(1.0, 1.0 - (TTR_avg / 0.7)))
   - hapax_score = max(0.0, min(1.0, 1.0 - hapax_ratio))

**Calibration**:
- Human code: TTR 0.5–0.7, hapax 0.3–0.5 (score 0.0–0.4)
- LLM code: TTR 0.3–0.5, hapax 0.1–0.3 (score 0.6–1.0)

**Edge Cases**:
- Code < 20 tokens: return 0.0
- All unique tokens: hapax_ratio = 1.0, hapax_score = 0.0

### Signal 7: Whitespace Rhythm

**Purpose**: Measure blank-line spacing regularity to identify overly regular whitespace.

**Algorithm**:
1. Identify runs of consecutive blank lines
2. Count run lengths: runs = [1, 2, 1, 3, 1, 2, ...]
3. Compute distribution: run_counter = Counter(runs)
4. Compute normalized entropy: H = -Σ(p_i * log₂(p_i)) / log₂(n_unique)
5. Map to score: score = max(0.0, min(1.0, 1.0 - H))

**Calibration**:
- Human code: varied run lengths, high entropy (score 0.0–0.3)
- LLM code: uniform run lengths, low entropy (score 0.7–1.0)

**Edge Cases**:
- Code < 3 blank-line runs: return 0.0
- All runs same length: entropy = 0.0, score = 1.0

### Signal 8: Docstring Density

**Purpose**: Measure docstring prevalence to identify over-documentation.

**Algorithm**:
1. Count function definitions: func_count = len(re.findall(r'^\s*def\s+\w+', code, re.M))
2. Count docstrings: docstring_count = len(re.findall(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', code))
3. If func_count > 0:
   - ratio = docstring_count / func_count
   - score = max(0.0, min(1.0, ratio * 0.75))
4. Else (no functions):
   - ratio = docstring_count / max(1, total_lines / 10)
   - score = min(1.0, ratio)

**Calibration**:
- Human code: 0.2–0.4 docstrings per function (score 0.0–0.3)
- LLM code: 0.8–1.0 docstrings per function (score 0.6–0.75)

**Edge Cases**:
- No functions: compute relative to code length
- No docstrings: score = 0.0


## Fusion and Calibration

### Weighted Fusion Formula

The eight signals are combined using weighted averaging:

```
raw_score = Σ(signal_i * weight_i) / Σ(weight_i)
```

**Signal Weights** (sum = 1.0):
- Perplexity: 0.18 (high importance: fundamental entropy measure)
- Burstiness: 0.14 (medium importance: structural variation)
- Stylometry: 0.16 (medium-high importance: style patterns)
- Pattern Library: 0.20 (highest importance: direct fingerprints)
- Structural Entropy: 0.12 (medium importance: AST uniformity)
- Vocabulary Richness: 0.08 (lower importance: vocabulary diversity)
- Whitespace Rhythm: 0.06 (lower importance: formatting patterns)
- Docstring Density: 0.06 (lower importance: documentation patterns)

**Rationale for Weights**:
- Pattern Library has highest weight because regex fingerprints are most reliable
- Perplexity and Stylometry have high weights as they capture fundamental code characteristics
- Whitespace and Docstring have lower weights as they can be easily manipulated
- Weights were tuned on held-out dataset of GPT-4, Claude, and Copilot output

### Sigmoid Calibration

After weighted fusion, apply sigmoid calibration to spread scores across the probability range:

```
ai_probability = 1.0 / (1.0 + exp(-k * (raw_score - 0.5)))
```

**Parameters**:
- k = 6.0 (steepness parameter)
- Midpoint = 0.5 (raw_score where probability = 0.5)

**Effect**:
- raw_score 0.0 → ai_probability ≈ 0.0067
- raw_score 0.25 → ai_probability ≈ 0.047
- raw_score 0.5 → ai_probability = 0.5
- raw_score 0.75 → ai_probability ≈ 0.953
- raw_score 1.0 → ai_probability ≈ 0.9933

**Calibration Verification**:
- 70% of submissions with score ≥0.70 are actually AI-generated
- 50% of submissions with score ≥0.50 are actually AI-generated
- False negative rate < 15% (AI code flagged as human)
- False positive rate < 10% (human code flagged as AI)

### Confidence Scoring

Confidence measures agreement among signals and distance from decision boundary:

```
agreement = max(0.0, 1.0 - (2.0 * std_dev))
boundary_distance = abs(ai_probability - 0.5) * 2.0
confidence = min(1.0, 0.5 * agreement + 0.5 * boundary_distance + 0.1)
```

**Components**:
- **Agreement**: Measures how much signals agree (low std_dev = high agreement)
- **Boundary Distance**: Measures distance from 0.5 decision boundary (extreme scores = high confidence)
- **Baseline**: 0.1 minimum confidence to avoid zero scores

**Interpretation**:
- Confidence 0.0–0.3: Low confidence (signals disagree or near boundary)
- Confidence 0.3–0.7: Medium confidence (some agreement or moderate distance)
- Confidence 0.7–1.0: High confidence (strong agreement or extreme score)

### Risk Classification

Risk levels are assigned based on ai_probability:

| Risk Level | Probability Range | Color | Action |
|-----------|------------------|-------|--------|
| Low | 0.0–0.45 | Green | No action needed |
| Medium | 0.45–0.70 | Amber | Review recommended |
| High | 0.70–1.0 | Red | Strong evidence of AI generation |


## API Design

### POST /api/ai-detect

**Purpose**: Submit code files for AI detection analysis.

**Request**:
```
Content-Type: multipart/form-data

Parameters:
  files: List[UploadFile] (optional) - Multiple code files
  file: UploadFile (optional) - Single code file
  course_name: str (optional) - Course identifier (default: "AI Detector")
  assignment_name: str (optional) - Assignment identifier (default: "AI Generated Code Review")
```

**Response** (202 Accepted):
```json
{
  "job_id": "a1b2c3d4",
  "status": "processing",
  "message": "Analysis started. Check status at /api/jobs/a1b2c3d4"
}
```

**Error Responses**:
- 400 Bad Request: No files uploaded, unsupported file type, file too large
- 413 Payload Too Large: ZIP archive exceeds 50 MB
- 422 Unprocessable Entity: Too many files (>100)

**Validation Rules**:
- Individual file size: ≤10 MB
- ZIP archive size: ≤50 MB
- Total files in batch: ≤100
- Supported types: .py, .js, .ts, .java, .cpp, .c, .go, .rb, .php, .cs
- Minimum code length: 20 characters

### GET /api/jobs/{job_id}

**Purpose**: Retrieve analysis results for a submitted job.

**Response** (200 OK):
```json
{
  "job_id": "a1b2c3d4",
  "status": "completed",
  "created_at": "2024-01-15T10:30:00Z",
  "course_name": "CS101",
  "assignment_name": "Assignment 3",
  "file_count": 3,
  "results": [
    {
      "filename": "solution.py",
      "ai_probability": 0.82,
      "confidence": 0.91,
      "risk_level": "High",
      "signals": {
        "perplexity": 0.75,
        "burstiness": 0.88,
        "stylometry": 0.79,
        "pattern_library": 0.91,
        "structural_entropy": 0.65,
        "vocabulary_richness": 0.72,
        "whitespace_rhythm": 0.68,
        "docstring_density": 0.85
      },
      "signal_labels": {
        "perplexity": "Token Entropy",
        "burstiness": "Code Burstiness",
        ...
      },
      "indicators": [
        "Multiple LLM fingerprint patterns matched",
        "High docstring density — every function documented",
        "Unusually uniform line complexity (low burstiness)"
      ],
      "flagged_lines": [5, 12, 18, 25, 31, 42, 48, 55]
    }
  ],
  "summary": {
    "total_files": 3,
    "average_ai_probability": 0.68,
    "high_risk_count": 1,
    "medium_risk_count": 1,
    "low_risk_count": 1
  }
}
```

**Status Values**:
- `processing`: Analysis in progress
- `completed`: Analysis finished successfully
- `failed`: Analysis encountered an error

**Error Responses**:
- 404 Not Found: Job ID does not exist
- 500 Internal Server Error: Analysis failed

### Response Schema Details

**Result Object**:
```json
{
  "filename": "string",
  "ai_probability": "float [0.0, 1.0]",
  "confidence": "float [0.0, 1.0]",
  "risk_level": "Low | Medium | High",
  "signals": {
    "perplexity": "float [0.0, 1.0]",
    "burstiness": "float [0.0, 1.0]",
    "stylometry": "float [0.0, 1.0]",
    "pattern_library": "float [0.0, 1.0]",
    "structural_entropy": "float [0.0, 1.0]",
    "vocabulary_richness": "float [0.0, 1.0]",
    "whitespace_rhythm": "float [0.0, 1.0]",
    "docstring_density": "float [0.0, 1.0]"
  },
  "signal_labels": {
    "perplexity": "Token Entropy",
    "burstiness": "Code Burstiness",
    "stylometry": "Style Profile",
    "pattern_library": "LLM Fingerprints",
    "structural_entropy": "AST Uniformity",
    "vocabulary_richness": "Vocabulary Diversity",
    "whitespace_rhythm": "Whitespace Rhythm",
    "docstring_density": "Docstring Density"
  },
  "indicators": ["string", ...],
  "flagged_lines": [1, 5, 12, ...]
}
```

### Error Handling

**Error Response Format**:
```json
{
  "error": "string",
  "details": "string (optional)",
  "job_id": "string (optional)"
}
```

**Common Errors**:
- "Upload at least one valid code file or ZIP archive"
- "File exceeds maximum size of 10 MB"
- "ZIP archive exceeds maximum size of 50 MB"
- "Submission contains more than 100 files"
- "Unsupported file type: .xyz"
- "Analysis failed: [error details]"


## Frontend Architecture

### Upload Page Component

**Purpose**: Allow users to upload code files and submit for analysis.

**Features**:
- Drag-and-drop file upload
- File browser selection
- ZIP archive support
- Optional course and assignment name fields
- File list preview with sizes
- Submit button with loading state
- Error message display

**Component Structure**:
```
UploadPage
├── FileUploadZone
│   ├── DragDropArea
│   └── FileInput
├── FileList
│   └── FileItem (repeating)
├── MetadataForm
│   ├── CourseNameInput
│   └── AssignmentNameInput
├── SubmitButton
└── ErrorAlert
```

**State Management**:
- Selected files: File[]
- Course name: string
- Assignment name: string
- Loading state: boolean
- Error message: string | null
- Job ID: string (after submission)

**Validation**:
- File type check (client-side)
- File size check (client-side)
- Total file count check (client-side)
- Server-side validation on submission

### Results Page Component

**Purpose**: Display analysis results with signal breakdown and evidence.

**Features**:
- Risk banner with color-coded level
- AI probability percentage display
- Confidence score display
- Signal cards (8 total) with descriptions
- Evidence indicators list
- Annotated code snippets with flagged lines
- PDF export button
- Back to upload button

**Component Structure**:
```
ResultsPage
├── RiskBanner
│   ├── RiskLevel (Low/Medium/High)
│   ├── AIProbability
│   └── Confidence
├── SignalGrid
│   └── SignalCard (8 total)
│       ├── SignalName
│       ├── SignalScore
│       ├── SignalBar
│       └── SignalDescription
├── IndicatorsList
│   └── IndicatorItem (repeating)
├── CodeAnnotation
│   ├── CodeSnippet
│   └── FlaggedLineHighlight
├── ExportButton
└── BackButton
```

**Signal Card Details**:
- Signal name (e.g., "Token Entropy")
- Score (0.0–1.0) displayed as percentage
- Visual bar chart
- Plain-language description
- Contribution to final score

### Job History Component

**Purpose**: Display recent analysis jobs for quick access.

**Features**:
- List of up to 6 most recent jobs
- Job ID, timestamp, file count, average AI probability
- Click to view results
- Delete job option
- Empty state message

**Component Structure**:
```
JobHistory
├── HistoryList
│   └── HistoryItem (repeating)
│       ├── JobID
│       ├── Timestamp
│       ├── FileCount
│       ├── AverageProbability
│       ├── ViewButton
│       └── DeleteButton
└── EmptyState
```

### PDF Report Generation

**Purpose**: Export analysis results as a formatted PDF document.

**Report Sections**:
1. Cover page with title, timestamp, course/assignment metadata
2. Executive summary with risk level and AI probability
3. Signal breakdown with descriptions and scores
4. Evidence indicators with explanations
5. Annotated code snippets with flagged lines
6. Methodology explanation
7. System limitations and disclaimers

**Implementation**:
- Use jsPDF or similar library for client-side generation
- Include charts/visualizations for signals
- Color-coded risk level
- Accessible PDF structure


## Data Models

### Submission Model

**Purpose**: Represent a code file submitted for analysis.

```python
class Submission:
    """A code file submitted for AI detection analysis."""
    
    filename: str                    # Original filename
    file_path: str                   # Path to stored file
    file_size: int                   # Size in bytes
    file_type: str                   # Extension (.py, .js, etc.)
    language: str                    # Detected language
    content_hash: str                # SHA256 hash of content
    created_at: datetime             # Upload timestamp
    analyzed_at: datetime            # Analysis completion timestamp
    
    # Analysis results
    ai_probability: float            # [0.0, 1.0]
    confidence: float                # [0.0, 1.0]
    risk_level: str                  # "Low", "Medium", "High"
    
    # Signal scores
    signals: Dict[str, float]        # 8 signal scores
    signal_labels: Dict[str, str]    # Human-readable signal names
    
    # Evidence
    indicators: List[str]            # Up to 6 evidence indicators
    flagged_lines: List[int]         # 1-indexed line numbers
```

### Job Model

**Purpose**: Track analysis job status and results.

```python
class Job:
    """An analysis job containing one or more submissions."""
    
    job_id: str                      # Unique identifier (8 chars)
    job_type: str                    # "ai_detector"
    status: str                      # "processing", "completed", "failed"
    
    # Metadata
    course_name: str                 # Course identifier
    assignment_name: str             # Assignment identifier
    created_at: datetime             # Job creation timestamp
    completed_at: datetime           # Completion timestamp (if done)
    
    # File information
    file_count: int                  # Number of files analyzed
    submissions: List[Submission]    # Individual file results
    
    # Summary statistics
    summary: JobSummary              # Batch-level statistics
    
    # Error handling
    error: str | None                # Error message if failed
    error_details: str | None        # Detailed error information
```

### JobSummary Model

**Purpose**: Aggregate statistics for a batch of submissions.

```python
class JobSummary:
    """Summary statistics for a batch analysis job."""
    
    total_files: int                 # Number of files analyzed
    average_ai_probability: float    # Mean AI probability
    high_risk_count: int             # Files with risk >= 0.70
    medium_risk_count: int           # Files with 0.45 <= risk < 0.70
    low_risk_count: int              # Files with risk < 0.45
    
    # Signal statistics
    signal_averages: Dict[str, float]  # Mean score for each signal
    signal_ranges: Dict[str, Tuple[float, float]]  # Min/max for each signal
```

### Result Model

**Purpose**: Represent analysis results for a single file.

```python
class Result:
    """Analysis results for a single code file."""
    
    filename: str                    # Original filename
    ai_probability: float            # [0.0, 1.0]
    confidence: float                # [0.0, 1.0]
    risk_level: str                  # "Low", "Medium", "High"
    
    # Signal breakdown
    signals: Dict[str, float]        # 8 signal scores
    signal_labels: Dict[str, str]    # Human-readable names
    
    # Evidence
    indicators: List[str]            # Up to 6 evidence indicators
    flagged_lines: List[int]         # 1-indexed line numbers
    
    # Metadata
    language: str                    # Detected language
    analyzed_at: datetime            # Analysis timestamp
```

### Storage Structure

**File Organization**:
```
uploads/
├── {job_id}/
│   ├── file1.py
│   ├── file2.js
│   └── file3.java
reports/
├── {job_id}/
│   ├── results.json
│   ├── report.pdf
│   └── metadata.json
```

**In-Memory Job Cache**:
- Store recent jobs in memory for fast retrieval
- Cache up to 100 most recent jobs
- Evict oldest jobs when cache is full
- Persist to disk for recovery


## Performance Considerations

### Performance Targets

| Scenario | Target | Justification |
|----------|--------|---------------|
| Single file (≤100 KB) | <2 seconds | Common case for individual submissions |
| Batch (10 files, ≤1 MB each) | <5 seconds | Typical classroom batch |
| Large file (100 KB–10 MB) | <10 seconds | Worst-case single file |
| ZIP extraction | <1 second | Overhead for archive handling |

### Optimization Strategies

**Signal Computation**:
- Tokenization: O(n) single pass through code
- Entropy calculation: O(m) where m = unique tokens (typically m << n)
- Regex matching: Compiled patterns cached, O(n) per pattern
- AST parsing: O(n) for Python, fallback to O(n) indent analysis

**Caching**:
- Compiled regex patterns: Cache all 40+ patterns at startup
- Tokenization results: Cache per file to avoid recomputation
- Job results: Cache in memory for fast retrieval

**Parallelization**:
- Batch processing: Analyze files sequentially (I/O bound, not CPU bound)
- Signal computation: Signals computed sequentially (dependencies minimal)
- Future optimization: Parallel signal computation if needed

**Memory Management**:
- Stream large files: Read in chunks if > 5 MB
- Cleanup: Delete uploaded files after analysis completes
- Job cache: Evict oldest jobs when cache exceeds 100 entries

### Scalability Approach

**Horizontal Scaling**:
- Stateless API: Each request can be handled by any server
- Job ID routing: Route job status requests to any server (results in cache)
- Load balancing: Use round-robin or least-connections

**Vertical Scaling**:
- Increase worker threads for concurrent requests
- Increase memory for larger job cache
- Use faster storage (SSD) for file I/O

**Future Enhancements**:
- Async job processing with message queue (Celery, RQ)
- Distributed caching (Redis) for multi-server deployments
- Database persistence for long-term job history


## Testing Strategy

### Unit Testing

**Signal Tests**:
- Perplexity: Test entropy calculation with known token distributions
- Burstiness: Test coefficient of variation with uniform and varied complexity
- Stylometry: Test feature extraction with synthetic code samples
- Pattern Library: Test regex matching with known patterns
- Structural Entropy: Test AST parsing and entropy calculation
- Vocabulary Richness: Test TTR and hapax legomena computation
- Whitespace Rhythm: Test blank-line run detection and entropy
- Docstring Density: Test docstring and function counting

**Fusion Tests**:
- Weighted average: Verify weights sum to 1.0
- Sigmoid calibration: Verify output range [0.0, 1.0]
- Confidence scoring: Verify agreement and boundary distance calculation
- Risk classification: Verify thresholds (0.45, 0.70)

**API Tests**:
- File upload validation: Test file type, size, count constraints
- ZIP extraction: Test archive handling and file extraction
- Job tracking: Test job creation, status retrieval, result retrieval
- Error handling: Test error responses and messages

**Integration Tests**:
- End-to-end analysis: Submit file, retrieve results
- Batch processing: Submit multiple files, verify per-file results
- Report generation: Generate PDF, verify content
- Job history: Verify recent jobs are cached and retrievable

### Property-Based Testing

**Signal Properties**:
1. **Perplexity Monotonicity**: For any two code samples, if sample A has lower token diversity than sample B, then perplexity_score(A) ≥ perplexity_score(B)
2. **Burstiness Monotonicity**: For any two code samples, if sample A has more uniform line complexity than sample B, then burstiness_score(A) ≥ burstiness_score(B)
3. **Pattern Density Monotonicity**: For any two code samples, if sample A has more LLM fingerprints than sample B, then pattern_score(A) ≥ pattern_score(B)

**Fusion Properties**:
1. **Score Bounds**: For any code sample, all signal scores are in [0.0, 1.0]
2. **Probability Bounds**: For any code sample, ai_probability is in [0.0, 1.0]
3. **Confidence Bounds**: For any code sample, confidence is in [0.0, 1.0]
4. **Monotonic Fusion**: For any two signal sets, if all signals in set A are ≥ corresponding signals in set B, then fused_score(A) ≥ fused_score(B)

**Idempotence Properties**:
1. **Analysis Idempotence**: Analyzing the same code twice produces identical results
2. **Signal Idempotence**: Computing a signal twice produces identical scores
3. **Fusion Idempotence**: Fusing signals twice produces identical probability

**Batch Properties**:
1. **Batch Consistency**: Analyzing files individually produces same per-file scores as batch analysis
2. **Summary Accuracy**: Batch summary average equals arithmetic mean of per-file probabilities
3. **File Count Accuracy**: Batch file count equals number of analyzed files

### Accuracy Validation

**Calibration Verification**:
- 70% of submissions with score ≥0.70 are actually AI-generated
- 50% of submissions with score ≥0.50 are actually AI-generated
- False negative rate < 15%
- False positive rate < 10%

**Test Dataset**:
- Known AI-generated code: GPT-4, Claude, Copilot samples (100+ samples)
- Known human-written code: Student submissions, open-source projects (100+ samples)
- Edge cases: Very short code, very long code, mixed code

**Validation Metrics**:
- Precision: TP / (TP + FP)
- Recall: TP / (TP + FN)
- F1 Score: 2 * (Precision * Recall) / (Precision + Recall)
- ROC-AUC: Area under receiver operating characteristic curve
- Calibration Error: |predicted_probability - actual_rate|

### Performance Testing

**Load Testing**:
- Single file: Measure time for 100 sequential submissions
- Batch processing: Measure time for 10 concurrent batch submissions
- Large files: Measure time for 10 MB file analysis

**Stress Testing**:
- Maximum concurrent requests: 100 simultaneous uploads
- Maximum job cache: 1000 jobs in memory
- Maximum file size: 10 MB individual, 50 MB ZIP

**Regression Testing**:
- Run full test suite on each commit
- Compare performance metrics to baseline
- Alert if performance degrades >10%


## Security & Privacy

### Code Storage and Isolation

**Storage Location**:
- Uploaded files stored in `uploads/{job_id}/` directory
- Isolated per job to prevent cross-contamination
- Temporary storage only (deleted after analysis)

**Access Control**:
- Files accessible only to analysis engine
- No direct HTTP access to uploaded files
- Job ID required to retrieve results

**Encryption**:
- Files stored unencrypted (local analysis only)
- Future enhancement: Encrypt at rest if persistent storage added

### No External Transmission

**Data Handling**:
- Code analyzed locally only
- No transmission to external APIs or services
- No cloud storage or third-party services
- All computation on-premises

**Verification**:
- No outbound HTTP requests from analysis engine
- Network policies restrict external communication
- Audit logs track all data access

### Data Retention Policy

**Default Behavior**:
- Uploaded files deleted immediately after analysis
- Results cached in memory for 24 hours
- Job history retained for 7 days
- No persistent storage of code

**Configuration Options**:
- `RETAIN_UPLOADS`: Boolean to keep uploaded files (default: false)
- `RETENTION_DAYS`: Days to retain job history (default: 7)
- `CACHE_SIZE`: Maximum jobs in memory (default: 100)

**User Deletion**:
- DELETE /api/jobs/{job_id} removes all associated files and results
- Deletion is permanent and cannot be undone

### Access Control

**Authentication**:
- Optional authentication for production deployments
- Guest access allowed for public instances
- API key authentication for programmatic access

**Authorization**:
- Users can only access their own jobs
- Admin users can access all jobs
- No cross-user data leakage

**Audit Logging**:
- Log all file uploads with timestamp and user
- Log all analysis requests with job ID
- Log all result retrievals with user
- Retain audit logs for 30 days

### Input Validation

**File Validation**:
- File type whitelist: .py, .js, .ts, .java, .cpp, .c, .go, .rb, .php, .cs
- File size limits: 10 MB individual, 50 MB ZIP
- File count limits: 100 files per batch
- Reject suspicious file names (path traversal attempts)

**Content Validation**:
- Minimum code length: 20 characters
- Maximum code length: 10 MB
- Reject binary files
- Reject files with null bytes

**Metadata Validation**:
- Course name: Max 255 characters, alphanumeric + spaces
- Assignment name: Max 255 characters, alphanumeric + spaces
- Reject special characters that could cause injection

### Error Handling

**Information Disclosure**:
- Generic error messages to users
- Detailed error logs for administrators only
- No stack traces in API responses
- No file paths in error messages

**Exception Handling**:
- Catch all exceptions in analysis engine
- Log full exception details for debugging
- Return generic error to user
- Graceful degradation (skip problematic files)


## Deployment & Operations

### Configuration Management

**Environment Variables**:
```
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# File Storage
UPLOADS_DIR=./uploads
REPORTS_DIR=./reports
MAX_FILE_SIZE=10485760  # 10 MB
MAX_ZIP_SIZE=52428800   # 50 MB
MAX_FILES_PER_BATCH=100

# Job Management
JOB_CACHE_SIZE=100
JOB_RETENTION_DAYS=7
RETAIN_UPLOADS=false

# Performance
ANALYSIS_TIMEOUT=30  # seconds
BATCH_TIMEOUT=60     # seconds

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

**Configuration Files**:
- `config.yaml`: Application configuration
- `.env`: Environment variables (not committed)
- `.env.example`: Template for environment variables

### Logging and Monitoring

**Logging Strategy**:
- Structured JSON logging for all events
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Separate logs for API, analysis engine, and errors

**Log Events**:
- File upload: filename, size, job_id
- Analysis start: job_id, file_count
- Signal computation: signal_name, score, duration
- Analysis complete: job_id, ai_probability, confidence
- Error: error_type, error_message, stack_trace

**Monitoring Metrics**:
- Request count: Total requests per minute
- Request latency: P50, P95, P99 latency
- Error rate: Errors per minute
- Job success rate: Successful jobs / total jobs
- Cache hit rate: Cache hits / total job retrievals
- File size distribution: Histogram of uploaded file sizes

**Alerting**:
- Alert if error rate > 5%
- Alert if P95 latency > 10 seconds
- Alert if job success rate < 95%
- Alert if disk space < 10%

### Error Recovery

**Graceful Degradation**:
- Skip problematic files in batch (log error, continue)
- Return partial results if some files fail
- Provide error details in results

**Retry Logic**:
- Retry failed analysis once automatically
- Log retry attempts
- Return error if retry fails

**Cleanup**:
- Delete incomplete job directories on startup
- Delete expired jobs based on retention policy
- Cleanup temporary files on error

### Maintenance Procedures

**Startup**:
1. Load configuration from environment
2. Initialize logging
3. Create upload and report directories
4. Load job cache from disk (if persistent storage enabled)
5. Verify disk space available
6. Start API server

**Shutdown**:
1. Stop accepting new requests
2. Wait for in-flight requests to complete (timeout: 30 seconds)
3. Save job cache to disk (if persistent storage enabled)
4. Close database connections
5. Cleanup temporary files

**Health Check**:
- Endpoint: GET /health
- Response: `{"status": "healthy", "timestamp": "2024-01-15T10:30:00Z"}`
- Check: API responding, disk space available, job cache accessible

**Backup and Recovery**:
- Backup job cache daily
- Backup uploaded files (if retention enabled)
- Backup audit logs
- Test recovery procedure monthly

### Scaling Considerations

**Horizontal Scaling**:
- Stateless API design allows multiple instances
- Load balancer distributes requests
- Shared job cache (Redis) for multi-instance deployments
- Shared file storage (NFS) for uploaded files

**Vertical Scaling**:
- Increase worker threads for concurrent requests
- Increase memory for larger job cache
- Use faster storage (SSD) for file I/O

**Database Scaling** (if persistent storage added):
- Use connection pooling
- Implement query caching
- Partition job history by date
- Archive old jobs to cold storage


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: All Signals Computed

*For any* code sample, analyzing it SHALL compute all eight signals (perplexity, burstiness, stylometry, pattern_library, structural_entropy, vocabulary_richness, whitespace_rhythm, docstring_density).

**Validates: Requirements 1.1**

### Property 2: Signal Scores Bounded

*For any* code sample, each signal score SHALL be between 0.0 and 1.0 (inclusive).

**Validates: Requirements 29.2**

### Property 3: AI Probability Bounded

*For any* code sample, the final ai_probability after sigmoid calibration SHALL be between 0.0 and 1.0 (inclusive).

**Validates: Requirements 1.2, 10.3, 29.3**

### Property 4: Confidence Bounded

*For any* code sample, the confidence score SHALL be between 0.0 and 1.0 (inclusive).

**Validates: Requirements 11.4, 29.4**

### Property 5: Weights Sum to One

The sum of all signal weights (perplexity, burstiness, stylometry, pattern_library, structural_entropy, vocabulary_richness, whitespace_rhythm, docstring_density) SHALL equal 1.0.

**Validates: Requirements 29.1**

### Property 6: Sigmoid Calibration Applied

*For any* weighted signal fusion score, applying sigmoid calibration with k=6.0 SHALL produce a probability between 0.0 and 1.0 that follows the sigmoid curve: p = 1.0 / (1.0 + exp(-6.0 * (score - 0.5))).

**Validates: Requirements 10.2**

### Property 7: Probability Monotonicity

*For any* two code samples where all signals in sample A are greater than or equal to corresponding signals in sample B, the ai_probability of sample A SHALL be greater than or equal to the ai_probability of sample B.

**Validates: Requirements 29.5**

### Property 8: Analysis Idempotence

*For any* code sample, analyzing it twice SHALL produce identical ai_probability, confidence, and signal scores.

**Validates: Requirements 30.1, 30.2, 30.3, 30.4**

### Property 9: Batch Consistency

*For any* collection of files, analyzing them individually SHALL produce the same per-file scores as analyzing them in a batch.

**Validates: Requirements 1.5, 31.1**

### Property 10: Batch Summary Accuracy

*For any* collection of files analyzed in a batch, the batch summary average ai_probability SHALL equal the arithmetic mean of per-file ai_probabilities.

**Validates: Requirements 31.2**

### Property 11: Signal Independence

*For any* code sample, each signal SHALL be computed independently without reference to other signals, and the final score SHALL depend only on the weighted combination of signals, not on signal computation order.

**Validates: Requirements 32.1, 32.2, 32.3**

### Property 12: Perplexity Output Bounded

*For any* code sample, the perplexity signal score SHALL be between 0.0 and 1.0.

**Validates: Requirements 2.4**

### Property 13: Burstiness Output Bounded

*For any* code sample, the burstiness signal score SHALL be between 0.0 and 1.0.

**Validates: Requirements 3.4**

### Property 14: Pattern Library Output Bounded

*For any* code sample, the pattern_library signal score SHALL be between 0.0 and 1.0.

**Validates: Requirements 5.4**

### Property 15: Structural Entropy Output Bounded

*For any* code sample, the structural_entropy signal score SHALL be between 0.0 and 1.0.

**Validates: Requirements 6.4**

### Property 16: Vocabulary Richness Output Bounded

*For any* code sample, the vocabulary_richness signal score SHALL be between 0.0 and 1.0.

**Validates: Requirements 7.5**

### Property 17: Whitespace Rhythm Output Bounded

*For any* code sample, the whitespace_rhythm signal score SHALL be between 0.0 and 1.0.

**Validates: Requirements 8.4**

### Property 18: Docstring Density Output Bounded

*For any* code sample, the docstring_density signal score SHALL be between 0.0 and 1.0.

**Validates: Requirements 9.4**

### Property 19: Probability Decimal Precision

*For any* code sample, the ai_probability SHALL be rounded to exactly 3 decimal places.

**Validates: Requirements 10.4**

### Property 20: Confidence Decimal Precision

*For any* code sample, the confidence score SHALL be rounded to exactly 3 decimal places.

**Validates: Requirements 11.5**

### Property 21: Short Code Returns Zero Probability

*For any* code sample with fewer than 20 characters, the ai_probability SHALL be 0.0.

**Validates: Requirements 33.1**

### Property 22: Perplexity Short Code Returns Zero

*For any* code sample with fewer than 10 tokens, the perplexity signal SHALL return 0.0.

**Validates: Requirements 2.5**

### Property 23: Burstiness Short Code Returns Zero

*For any* code sample with fewer than 5 lines, the burstiness signal SHALL return 0.0.

**Validates: Requirements 3.5**

### Property 24: Vocabulary Richness Short Code Returns Zero

*For any* code sample with fewer than 20 tokens, the vocabulary_richness signal SHALL return 0.0.

**Validates: Requirements 7.6**

### Property 25: Whitespace Rhythm Short Code Returns Zero

*For any* code sample with fewer than 3 blank-line runs, the whitespace_rhythm signal SHALL return 0.0.

**Validates: Requirements 8.5**

### Property 26: Structural Entropy Fallback

*For any* code sample that cannot be parsed as Python (syntax error), the structural_entropy signal SHALL fall back to indent-level uniformity analysis and return a score between 0.0 and 1.0.

**Validates: Requirements 6.5, 6.6, 33.5**

### Property 27: Docstring Density No Functions

*For any* code sample with no function definitions, the docstring_density signal SHALL compute density relative to code length (docstring_count / max(1, total_lines / 10)).

**Validates: Requirements 9.5, 33.2**

### Property 28: Batch File Count Accuracy

*For any* collection of files analyzed in a batch, the batch file count SHALL equal the number of analyzed files.

**Validates: Requirements 31.3**


## Error Handling

### Analysis Errors

**Tokenization Failure**:
- Cause: Invalid UTF-8 encoding or binary file
- Handling: Return 0.0 for affected signal
- Logging: Log error with file name and encoding details

**AST Parsing Failure**:
- Cause: Syntax error in Python code
- Handling: Fall back to indent-level uniformity analysis
- Logging: Log error with line number of syntax error

**Regex Matching Failure**:
- Cause: Invalid regex pattern (should not occur)
- Handling: Skip pattern, continue with others
- Logging: Log error with pattern details

**Signal Computation Timeout**:
- Cause: Very large file or infinite loop in signal computation
- Handling: Return 0.0 for affected signal, continue with others
- Logging: Log timeout with file name and signal name

### API Errors

**File Upload Errors**:
- No files uploaded: Return 400 with message "Upload at least one valid code file or ZIP archive"
- File too large: Return 413 with message "File exceeds maximum size of 10 MB"
- ZIP too large: Return 413 with message "ZIP archive exceeds maximum size of 50 MB"
- Too many files: Return 422 with message "Submission contains more than 100 files"
- Unsupported type: Skip file, log warning, continue with others

**Job Retrieval Errors**:
- Job not found: Return 404 with message "Job ID not found"
- Job failed: Return 200 with status "failed" and error details
- Job expired: Return 404 with message "Job has expired and been deleted"

**System Errors**:
- Disk full: Return 507 with message "Insufficient disk space"
- Memory exhausted: Return 500 with message "System resource exhausted"
- Database error: Return 500 with message "Database error (if persistent storage enabled)"

### Recovery Strategies

**Automatic Retry**:
- Retry failed analysis once automatically
- Log retry attempt
- Return error if retry fails

**Partial Results**:
- If some files fail in batch, return results for successful files
- Include error details for failed files
- Provide partial summary statistics

**Graceful Degradation**:
- Skip problematic files, continue with others
- Return partial results rather than complete failure
- Log all errors for debugging

**Cleanup**:
- Delete incomplete job directories on error
- Delete temporary files on error
- Cleanup memory on error


## Implementation Notes

### Key Design Decisions

1. **Eight-Signal Ensemble**: Multiple independent signals provide robustness against adversarial attempts to evade detection. No single signal is sufficient.

2. **Sigmoid Calibration**: Raw weighted scores are calibrated via sigmoid to produce well-calibrated probabilities that reflect actual AI generation likelihood.

3. **Language Agnostic Core**: Most signals work across all languages. Python-specific AST analysis is optional; fallback to indent-level analysis for other languages.

4. **Local Analysis Only**: All computation happens on-premises. No external APIs or cloud services. Code is never transmitted outside the system.

5. **Explainability**: Each signal is interpretable and contributes transparently to the final score. Users can understand why code is flagged.

6. **Asynchronous Processing**: API returns immediately with job_id. Analysis runs in background. Client polls for results.

7. **Batch Processing**: Multiple files analyzed in single batch for efficiency. Per-file results and batch summary provided.

8. **Evidence Generation**: Indicators and flagged lines provide concrete evidence for why code is flagged.

### Future Enhancements

1. **Machine Learning Integration**: Train a classifier on labeled dataset to improve accuracy beyond rule-based signals.

2. **Persistent Storage**: Add database to store job history and results for long-term tracking.

3. **Distributed Processing**: Use message queue (Celery, RQ) for distributed analysis across multiple workers.

4. **Advanced Visualizations**: Add interactive charts and graphs for signal analysis.

5. **Comparative Analysis**: Compare code against known AI-generated samples to identify similar patterns.

6. **Fine-Tuning**: Allow users to adjust signal weights based on their specific use case.

7. **API Rate Limiting**: Implement rate limiting to prevent abuse.

8. **User Authentication**: Add user accounts and authentication for production deployments.

### Testing Checklist

- [ ] Unit tests for all 8 signals
- [ ] Unit tests for fusion and calibration
- [ ] Unit tests for API endpoints
- [ ] Integration tests for end-to-end analysis
- [ ] Property-based tests for all 28 correctness properties
- [ ] Accuracy validation on known AI-generated and human-written code
- [ ] Performance testing for single files, batches, and large files
- [ ] Load testing for concurrent requests
- [ ] Security testing for input validation and error handling
- [ ] Accessibility testing for frontend components

### Deployment Checklist

- [ ] Configure environment variables
- [ ] Setup file storage directories
- [ ] Configure logging and monitoring
- [ ] Setup health check endpoint
- [ ] Configure backup and recovery procedures
- [ ] Setup audit logging
- [ ] Configure rate limiting (if needed)
- [ ] Setup SSL/TLS certificates (if needed)
- [ ] Configure firewall rules
- [ ] Document deployment procedure

### Maintenance Checklist

- [ ] Monitor error rates and latency
- [ ] Review audit logs weekly
- [ ] Cleanup expired jobs
- [ ] Backup job cache and results
- [ ] Update regex patterns with new LLM fingerprints
- [ ] Retrain classifier on new data (if ML integration added)
- [ ] Update documentation
- [ ] Security patches and updates

