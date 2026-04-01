# IntegrityDesk - Product Requirements Document

**Version**: 2.0
**Last Updated**: 2026-03-31
**Status**: Active Development

---

## 1. Executive Summary

**IntegrityDesk** is an enterprise-grade code plagiarism detection system designed to surpass industry leaders (MOSS, Copyleaks, Turnitin) by combining:

- **MOSS-style Winnowing** for fast fingerprinting
- **AST + Graph Matching** for structural similarity
- **LLM Semantic Analysis** for logic equivalence
- **AI Detection** for machine-generated code
- **Global Code Database** for source detection

**Target**: Academic institutions, coding bootcamps, enterprise code review, and compliance agencies.

---

## 2. Core Detection Engine

### 2.1 Algorithm Fusion (Surpassing MOSS Limitations)

#### Winnowing Fingerprints (MOSS-style)
- **k-gram hashing**: k=9-15 configurable
- **Window size**: w=64 for optimal coverage
- **Minimum hash selection**: Resistant to variable renaming
- **Preprocessing**: Strip whitespace, comments, normalize identifiers

#### AST + Graph Matching
- **Control Flow Graph (CFG)**: Extract basic blocks and edges
- **Data Flow Graph (DFG)**: Track variable dependencies
- **Graph Edit Distance (GED)**: GED < 0.2 flagged as plagiarism
- **Subtree Pattern Matching**: Detect code clones

#### LLM Semantic Analysis (Surpassing Copyleaks)
- **Logic Equivalence Detection**: Analyze `for` vs `while` equivalence
- **AI-Generated Detection**: Perplexity + Burstiness scoring
- **Multi-Model Fingerprinting**: Detect GPT/Gemini/Llama outputs
- **Confidence Intervals**: Statistical bounds on similarity scores

#### Normalization & Deobfuscation
- **Identifier Normalization**: Replace variable/function names with placeholders
- **Dead Code Removal**: Pre-analysis cleanup
- **String Normalization**: Hash literal strings
- **Import Standardization**: Normalize import order/style

### 2.2 Supported Languages (50+)

| Category | Languages |
|----------|-----------|
| **Web** | JavaScript, TypeScript, HTML, CSS, PHP, Ruby |
| **Systems** | C, C++, Rust, Go, Assembly |
| **JVM** | Java, Kotlin, Scala, Clojure, Groovy |
| **Functional** | Python, Haskell, OCaml, Elixir, Erlang, Scheme, Lisp |
| **Scripting** | Perl, Lua, Bash, PowerShell, R |
| **Data** | SQL, Julia, MATLAB |
| **Hardware** | Verilog, VHDL, Arduino |
| **Legacy** | Pascal, Fortran, COBOL, Ada, Prolog |

**Auto-detection**: Language detected from file extension and content analysis.

### 2.3 Code Database

#### Internal Sources
- **GitHub Mirror**: Daily sync of 10M+ public repositories
- **Stack Overflow**: Code snippet index from accepted answers
- **Academic Papers**: arXiv, IEEE, ACM code repositories
- **User Submission Pool**: Anonymous submission archive

#### External APIs
- **GitHub Gist Search**: Real-time gist matching
- **npm/PyPI/CRAN**: Package code analysis
- **Custom Integrations**: Enterprise codebases via API

### 2.4 Accuracy Targets

| Metric | Target |
|--------|--------|
| **Overall Accuracy** | >99% |
| **False Positive Rate** | <1% |
| **Precision (ROC)** | >0.98 |
| **Recall** | >0.99 |
| **Threshold (Default)** | >20% similarity = Alert |

---

## 3. Visualization & Reporting System

### 3.1 Report Types

#### Side-by-Side Highlighting
- Code line alignment with synchronized scrolling
- Color gradient: Red (100%) → Orange (50%) → Green (0%)
- Click-to-jump: Navigate from match to source
- Annotation tools: Add instructor notes

#### Similarity Heatmap
- File-level matrix: N×N comparison grid
- Function-level: Per-function similarity scores
- **Network Graph**: Plagiarism chain visualization (A→B→C)

#### AI Detection Report
- **AI Percentage**: Estimated % of AI-generated content
- **Confidence Interval**: Statistical bounds (e.g., 95% CI: [85%, 92%])
- **Paraphrase Score**: Detection of rephrased AI content
- **Model Fingerprint**: Identified LLM (GPT-4, Claude, Gemini, Llama)

#### License Risk Assessment
- **License Conflict Detection**: GPL vs MIT incompatibilities
- **Attribution Warnings**: Missing copyright notices
- **Compliance Score**: Overall license compliance rating

### 3.2 Export Formats

| Format | Features |
|--------|----------|
| **PDF** | Watermarked, tamper-proof, digital signature |
| **HTML** | Interactive, self-contained, offline-capable |
| **JSON** | API-ready, machine-parseable |
| **CSV** | Spreadsheet-compatible matrix export |

### 3.3 Real-Time Preview

- **Instant Scan**: Results as files upload (<10s for <1MB)
- **Batch Processing**: <5min for 100 files, <1h for 10k files
- **Progress Tracking**: Real-time percentage completion

---

## 4. Anti-Circumvention & Advanced Detection

### 4.1 Behavioral Fingerprinting

#### Git Blame Integration
- **Edit History**: Track who modified which lines
- **Author Attribution**: Link code segments to specific authors
- **Timeline Analysis**: Detect sudden large insertions

#### Typing Pattern Analysis
- **Keystroke Dynamics**: Detect copy-paste patterns
- **AI Typing Signals**: Uniform timing = machine-generated

### 4.2 Cross-Variant Detection

#### Template Matching
- **Algorithm Variants**: Detect insertion sort vs quicksort equivalence
- **Pattern Library**: Common assignment templates
- **Structural Fingerprints**: Hash of algorithm skeleton

#### Machine Learning Clustering
- **Intent Classification**: Group semantically similar code
- **Anomaly Detection**: Flag outliers in submission pool
- **Similarity Graph**: K-means clustering of submission clusters

### 4.3 AI-Detection "Killer" Features

- **Prompt Trail Detection**: Identify instruct/prompt remnants
- **Multi-Model Detection**: Separate GPT-4, Claude, Gemini, Llama signatures
- **Manual Re-entry Detection**: Even retyped AI content flagged
- **Style Transfer Resistance**: Detection survives paraphrasing

### 4.4 Batch Mode

- **N×N Comparison**: Complete pairwise analysis
- **Auto-clustering**: Group suspicious submissions automatically
- **Priority Queue**: Fast-track high-similarity pairs
- **Distributed Processing**: Horizontal scaling via Celery

---

## 5. Integration & Automation

### 5.1 Plugins & Extensions

| Platform | Integration |
|----------|-------------|
| **VCS** | GitHub Actions, GitLab CI, Bitbucket Pipelines |
| **IDE** | VSCode Extension, Jupyter Notebook Plugin |
| **LMS** | Moodle, Blackboard, Canvas, Brightspace |
| **Editor** | Vim/Neovim, Emacs, IntelliJ |
| **Communication** | Slack, Microsoft Teams notifications |

### 5.2 API Specifications

#### REST API
```
POST /api/v1/analyze          # Submit files for analysis
GET  /api/v1/results/{id}     # Retrieve results
GET  /api/v1/report/{id}      # Download report
POST /api/v1/webhooks         # Register webhook
GET  /api/v1/usage            # Usage metrics
```

#### GraphQL API
- Flexible querying for custom integrations
- Real-time subscriptions for result updates

#### Rate Limits
| Tier | Requests/min | Files/submission |
|------|--------------|-------------------|
| Free | 10 | 50 |
| Pro | 100 | 500 |
| Enterprise | Unlimited | Unlimited |

### 5.3 Webhook Events

```json
{
  "event": "analysis.complete",
  "submission_id": "uuid",
  "timestamp": "ISO8601",
  "similarity_score": 0.85,
  "ai_detected": true,
  "report_url": "https://..."
}
```

### 5.4 Self-Hosted Deployment

- **Docker Compose**: One-command deployment
- **Kubernetes Helm Chart**: Production scaling
- **Local Database**: SQLite for small deployments
- **Air-Gapped Mode**: No external dependencies

### 5.5 Automation

- **CI/CD Gates**: PR/block merge on threshold violation
- **Scheduled Scans**: Nightly batch analysis
- **Webhook Triggers**: LMS assignment deadline sync
- **Slack/Email Alerts**: Real-time plagiarism notifications

---

## 6. Exclusive Features

### 6.1 Collaboration Mode

#### Instructor Dashboard
- Class overview with similarity distribution
- Drill-down to individual students
- Bulk actions (flag, exonerate, export)
- Comment threads on specific code sections

#### Student Portal
- **Self-Check**: Pre-submission plagiarism scan
- **Feedback Loop**: Improvement suggestions
- **Citation Guide**: How to properly reference code
- **Progress Tracking**: Historical submission scores

### 6.2 Multi-Modal Analysis

- **Image OCR**: Detect code in screenshots/handwritten notes
- **Binary Reverse Engineering**: Compare compiled executables
- **PDF Code Extraction**: Pull code from research papers

### 6.3 Global Compliance Module

| Region | Compliance |
|--------|------------|
| **EU** | GDPR data isolation, right-to-erasure |
| **US** | FERPA student record protection |
| **Asia** | PDPA, China PIPL compliance |
| **Global** | SOC2, ISO 27001 certification |

#### Multi-Language Reports
- English (default)
- Chinese (中文)
- Japanese (日本語)
- Spanish, French, German, Portuguese

#### Privacy Features
- **Zero-Knowledge Proofs**: Verify without exposing code
- **On-Premises Processing**: Data never leaves environment
- **Encryption at Rest**: AES-256 for all stored code

### 6.4 Educational Tools

- **Tutorial System**: Interactive plagiarism awareness training
- **Simulation Sandbox**: Practice detecting/creating plagiarism
- **Citation Generator**: Auto-generate code references
- **Integrity Score**: Student historical compliance rating

### 6.5 Enterprise Extensions

- **Team Collaboration**: Shared workspaces with RBAC
- **Audit Logging**: Full immutable action history
- **SLA Guarantee**: 99.99% uptime with status page
- **Dedicated Support**: Priority ticket resolution
- **Custom Integrations**: Tailored API development

---

## 7. Business Model

### 7.1 Open-Source Core

- **License**: MIT (core engine)
- **Free Usage**: Unlimited for academic/research
- **Self-Hosted**: No feature limitations

### 7.2 Paid Tiers

| Feature | Free | Pro ($29/mo) | Enterprise (Custom) |
|---------|------|--------------|---------------------|
| Submissions/mo | 100 | 10,000 | Unlimited |
| Storage | 1GB | 100GB | Custom |
| API Access | Limited | Full | Full |
| Webhooks | ❌ | ✅ | ✅ |
| AI Detection | Basic | Advanced | Advanced+ |
| Priority Support | ❌ | ✅ | Dedicated |
| SSO/SAML | ❌ | ❌ | ✅ |
| Custom Branding | ❌ | ❌ | ✅ |

### 7.3 Revenue Streams

1. **Subscription Revenue**: Monthly/annual plans
2. **Credit Packs**: $0.01 per file (overage)
3. **White-Label**: Custom domain + branding
4. **Professional Services**: Setup, training, consulting

---

## 8. Technical Stack

### 8.1 Backend

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | Python 3.12+ / FastAPI | High-performance async API |
| **Parser** | Tree-sitter | Language-agnostic AST parsing |
| **Graph Analysis** | NetworkX | CFG/DFG similarity |
| **Machine Learning** | PyTorch | ML clustering, anomaly detection |
| **LLM Integration** | OpenAI/Anthropic API | Semantic analysis |
| **Task Queue** | Celery + Redis | Distributed processing |
| **Database** | PostgreSQL 16 + pgvector | Relational + vector similarity |
| **Cache** | Redis 7 | Session, results, rate limiting |
| **Search** | Elasticsearch | Full-text code search |

### 8.2 Frontend

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | React 18 + TypeScript | Component-based UI |
| **State** | Zustand / React Query | Client state management |
| **Visualization** | D3.js + Three.js | Network graphs, heatmaps |
| **Styling** | Tailwind CSS | Utility-first design |
| **Charts** | Recharts | Data visualization |

### 8.3 Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Container** | Docker + Compose | Local dev/deployment |
| **Orchestration** | Kubernetes | Production scaling |
| **CI/CD** | GitHub Actions | Automated testing/deployment |
| **Monitoring** | Prometheus + Grafana | Metrics & alerting |
| **Logging** | ELK Stack | Centralized logs |
| **CDN** | Cloudflare | Global static asset delivery |

### 8.4 Testing

| Type | Tool | Coverage Target |
|------|------|----------------|
| **Unit** | pytest | >90% |
| **Integration** | pytest + CI | 100% API endpoints |
| **Benchmark** | BigCloneBench | 18 test cases |
| **A/B Testing** | LaunchDarkly | Accuracy comparison |
| **Fuzzing** | AFL | Parser robustness |

---

## 9. Roadmap

### Phase 1: MVP (Current)
- [x] Core Winnowing algorithm
- [x] AST parsing (20+ languages)
- [x] REST API with authentication
- [x] Webhook delivery
- [x] Redis caching
- [x] Basic report generation
- [x] Simple Web GUI

### Phase 2: Enhanced Detection (Q2 2026)
- [ ] LLM semantic analysis integration
- [ ] AI-generated code detection
- [ ] Git blame analysis
- [ ] Batch processing (10k files)
- [ ] Enterprise SSO (SAML/OIDC)

### Phase 3: Intelligence (Q3 2026)
- [ ] Graph Edit Distance algorithm
- [ ] ML-based clustering
- [ ] Global code database (GitHub mirror)
- [ ] Real-time collaborative review
- [ ] Multi-modal analysis (images, binary)

### Phase 4: Enterprise (Q4 2026)
- [ ] White-label deployment
- [ ] GDPR compliance module
- [ ] Advanced audit logging
- [ ] Custom model training
- [ ] On-premises air-gapped version

---

## 10. Competitive Analysis

| Feature | IntegrityDesk | MOSS | Copyleaks | Turnitin |
|---------|---------------|------|-----------|----------|
| **Winnowing** | ✅ | ✅ | ❌ | ❌ |
| **AST Analysis** | ✅ | ✅ | Basic | ❌ |
| **LLM Semantic** | ✅ | ❌ | ✅ | ❌ |
| **AI Detection** | ✅ | ❌ | ✅ | ✅ |
| **Git Integration** | ✅ | ❌ | ❌ | ❌ |
| **Graph Matching** | ✅ | ❌ | ❌ | ❌ |
| **50+ Languages** | ✅ | ✅ | ✅ | ❌ |
| **REST API** | ✅ | ❌ | ✅ | Limited |
| **Self-Hosted** | ✅ | ✅ | ❌ | ❌ |
| **Webhook Events** | ✅ | ❌ | ✅ | ❌ |
| **Open Source** | ✅ (Core) | ❌ | ❌ | ❌ |
| **Global DB** | Planned | ❌ | ❌ | ✅ |

---

## 11. Glossary

| Term | Definition |
|------|------------|
| **Winnowing** | Fingerprinting algorithm using k-grams and minimum hashes |
| **AST** | Abstract Syntax Tree - parsed code representation |
| **CFG** | Control Flow Graph - program execution paths |
| **GED** | Graph Edit Distance - measure of graph similarity |
| **Perplexity** | Measure of randomness in text (AI detection) |
| **Burstiness** | Variance in sentence length (AI detection) |
| **False Positive** | Legitimate code flagged as plagiarism |
| **False Negative** | Plagiarism not detected |

---

## 12. Appendix

### A. Reference Standards
- ACM Code of Ethics
- IEEE Plagiarism Guidelines
- FERPA Student Privacy Requirements
- GDPR Data Protection Regulation

### B. Related Documents
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [DATABASE_DESIGN.md](./DATABASE_DESIGN.md) - Data model
- [TECH_CHOICES.md](./TECH_CHOICES.md) - Technology justification

### C. Contact
- **Email**: support@codeprovenance.io
- **GitHub**: https://github.com/tianzesun/IntegrityDesk
- **Documentation**: https://docs.codeprovenance.io