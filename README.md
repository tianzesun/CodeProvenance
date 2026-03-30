# CodeProvenance

A System for Detecting Software Similarity

## Overview

CodeProvenance is a backend service designed to detect software similarity between code submissions, similar to MIT's MOSS (Measure of Software Similarity) system. This service operates as a background processing component that can be integrated into grading platforms to help educators identify potential code plagiarism or similarity across student submissions.

## Key Features

- **Submission Comparison**: Analyzes and compares code submissions within a class to detect similarities
- **Background Service**: Runs as a non-GUI backend service, designed to be consumed by external grading platforms
- **RESTful API**: Provides programmatic interface for integration with other systems
- **Scalable Architecture**: Can handle multiple comparison requests concurrently

## Usage

The service accepts a folder containing all student submissions and returns similarity analysis results. It is designed to be called by other platforms rather than used directly by end users.

### Typical Workflow

1. Upload a folder containing all submissions to compare
2. The service processes and analyzes the code files
3. Receive similarity reports or scores for each submission pair

## Integration

CodeProvenance is not a standalone application with a GUI or web interface. It is intended to be integrated as a backend service component within larger grading or learning management systems.

## API

The service provides endpoints for:
- Submitting code folders for comparison
- Retrieving similarity analysis results
- Managing service configuration

## Competitive Analysis

CodeProvenance is a modern, API-first code similarity detection service inspired by **MIT's MOSS (Measure of Software Similarity)** system. Here's how we compare:

### Feature Comparison Table

| Feature | CodeProvenance | MOSS | Scribbr | Copyleaks | Grammarly |
|---------|----------------|------|---------|-----------|-----------|
| **Target Audience** | B2B SaaS Platforms | Academic Institutions | Students/Researchers | General Users | General Users |
| **Primary Use Case** | Code plagiarism detection | Code plagiarism detection | Text/Code plagiarism | Text/Code plagiarism | Grammar/Plagiarism |
| **API Access** | ✅ Full REST API | ❌ CLI only | ❌ Web only | ✅ Limited API | ✅ Limited API |
| **Multi-tenancy** | ✅ Row-level security | ❌ Not supported | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| **Webhook Events** | ✅ Real-time notifications | ❌ Not supported | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| **Deployment** | Self-hosted or cloud | Self-hosted only | Cloud only | Cloud only | Cloud only |
| **Pricing Model** | Usage-based | Free (academic) | Free/Premium | Subscription | Subscription |
| **Code AST Analysis** | ✅ Deep parsing | ✅ Deep parsing | ❌ Basic | ❌ Basic | ❌ No |
| **Winnowing Algorithm** | ✅ | ✅ | ❌ | ❌ | ❌ |

### Code-Specific Features

 | Feature | CodeProvenance | MOSS |
 |---------|----------------|------|
 | **Python** | ✅ | ✅ |
 | **Java** | ✅ | ✅ |
 | **C/C++** | ✅ | ✅ |
 | **Go** | ✅ | ✅ |
 | **Rust** | ✅ | ✅ |
 | **JavaScript/TypeScript** | ✅ | ✅ |
 | **C#** | ✅ | ✅ |
 | **Ruby** | ✅ | ✅ |
 | **Perl** | ✅ | ✅ |
 | **Haskell** | ✅ | ✅ |
 | **OCaml/ML** | ✅ | ✅ |
 | **Pascal** | ✅ | ✅ |
 | **Arduino** | ✅ | ✅ |
 | **Julia** | ✅ | ✅ |
 | **Scala** | ✅ | ✅ |
 | **SQL** | ✅ | ✅ |
 | **Scheme** | ✅ | ✅ |
 | **Blaise** | ✅ | ✅ |
 | **Forth** | ✅ | ✅ |
 | **ADABS** | ✅ | ✅ |
 
### Detection Algorithms

 | Algorithm | CodeProvenance | MOSS |
 |-----------|----------------|------|
 | **K-gram Token Matching** | ✅ | ✅ |
 | **Winnowing** | ✅ | ✅ |
 | **AST-based Comparison** | ✅ (All languages) | ✅ |
 | **N-gram Analysis** | ✅ | ✅ |
 | **Longest Common Subsequence** | ✅ | ✅ |
 | **Embedding-based (AI)** | ✅ | ❌ |

### Deep Code Analysis

CodeProvenance includes advanced deep analysis capabilities for detecting sophisticated plagiarism:

 | Algorithm | Description | Benefit |
 |-----------|--------------|---------|
 | **Tree Edit Distance (TED)** | Zhang-Shasha algorithm | Detects structural changes |
 | **Tree Kernel Similarity** | Subtree pattern matching | Identifies code clones |
 | **Normalized AST Comparison** | Variable renaming insensitive | Catches refactored plagiarism |
 | **Control Flow Analysis** | CFG comparison | Detects algorithmic similarity |
 | **Pattern Clone Detection** | Common structure patterns | Identifies copied patterns |
 | **Structural Fingerprinting** | AST-based hashes | Fast approximate matching |
 | **Complexity Metrics** | Cyclomatic complexity, depth | Detects copied complexity patterns |
 | **AI-Generated Detection** | Heuristic + statistical analysis | Identifies LLM-generated code |

### Enterprise Features

| Feature | CodeProvenance | MOSS |
|---------|----------------|------|
| **Rate Limiting** | ✅ Redis-based | ❌ Not needed |
| **Usage Metering** | ✅ Per-tenant tracking | ❌ Not needed |
| **Audit Logging** | ✅ Full audit trail | ❌ Not supported |
| **SSO/OAuth** | 🔜 Phase 2 | ❌ Not supported |
| **Role-based Access** | ✅ | ❌ Not supported |
| **Custom Thresholds** | ✅ API configurable | ❌ Fixed |
| **Webhook Retries** | ✅ Exponential backoff | ❌ Not supported |
| **HMAC Signatures** | ✅ SHA-256 | ❌ Not supported |

### Why CodeProvenance?

- **B2B SaaS Ready**: Built for integration into commercial grading platforms
- **Webhook Integration**: Real-time notifications for analysis completion
- **Usage Metering**: Track API usage for billing purposes
- **Rate Limiting**: Tier-based rate limiting with Redis
- **Smart Caching**: Redis-based caching for parsed ASTs and similarity results (7-day TTL)
- **Modern Stack**: FastAPI + PostgreSQL + Redis + Celery

### Performance Features

| Feature | Description |
|---------|-------------|
| **Parsed Code Cache** | Cache AST results to avoid re-parsing identical files |
| **Similarity Result Cache** | Cache pairwise similarity results |
| **Batch Comparison Cache** | Cache batch comparison results |
| **Fingerprint Cache** | Cache winnowing fingerprints |
| **File Cache Fallback** | Automatic disk-based cache when Redis unavailable |
| **Batch Processing** | Distributed Celery workers for large submission sets |
| **Incremental Updates** | Only compare new/changed files |

### Report Generation

Generate comprehensive similarity reports in multiple formats:

| Format | Description | Use Case |
|--------|-------------|----------|
| **HTML Report** | Interactive web-based report with filtering | Instructor review |
| **JSON Report** | Structured data for programmatic access | API integrations |
| **CSV Matrix** | Spreadsheet-compatible similarity matrix | Data analysis |
| **PDF Report** | Print-ready professional report | Academic integrity reviews |

## Web GUI

CodeProvenance includes a simple MOSS-like web interface for direct file analysis:

### Running the GUI

```bash
# Install GUI dependencies
pip install -r requirements-gui.txt

# Start the web server
python src/web_gui.py
```

Open http://localhost:5000 in your browser to use the GUI:

- **Drag & drop** code files for analysis
- **View results** in a text box (MOSS-style)
- **Export** reports in JSON/CSV/HTML formats

### GUI Features

| Feature | Description |
|---------|-------------|
| File Upload | Drag & drop or browse for multiple files |
| Auto-detection | Automatically detects programming language |
| Results Display | Shows similarity percentages and matches |
| Export Options | Download results as JSON, CSV, or HTML |
| Match Highlighting | View matched code sections side-by-side |

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
