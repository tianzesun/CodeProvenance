# CodeProvenance - Product Requirements Document (PRD)

## 1. Overview

**Project Name:** CodeProvenance  
**Project Type:** Backend Service (No GUI, No Web Interface)  
**Core Functionality:** Software similarity detection system for academic submissions  
**Target Users:** Grading platforms, educational institutions, instructors  

---

## 2. Problem Statement

Instructors need to identify potential plagiarism or similarity between student code submissions in programming assignments. Manual review is time-consuming and error-prone.

**Goals:**
- Automate code similarity detection
- Provide actionable similarity reports
- Integrate seamlessly with existing grading platforms

---

## 3. User Stories & Requirements

### 3.1 Core User Stories

| ID | Story | Priority |
|----|-------|----------|
| US-01 | As a platform, I can upload a folder containing multiple student submissions | P0 |
| US-02 | As a platform, I can configure similarity thresholds | P0 |
| US-03 | As a platform, I can retrieve similarity results for all submission pairs | P0 |
| US-04 | As a platform, I can filter results by similarity score | P1 |
| US-05 | As a platform, I can specify supported programming languages | P1 |
| US-06 | As a platform, I can configure file extensions to analyze | P1 |

### 3.2 Functional Requirements

#### 3.2.1 Submission Upload
- Accept: Folder path or ZIP file containing submissions
- Each submission should be in its own subfolder
- Support common archive formats: ZIP, TAR.GZ
- Maximum folder size: [TBD - default 100MB]
- Maximum single file size: [TBD - default 5MB]

#### 3.2.2 Supported Languages
Initial support:
- [ ] Python (.py)
- [ ] Java (.java)
- [ ] JavaScript (.js)
- [ ] C/C++ (.c, .cpp, .h)
- [ ] C# (.cs)
- [ ] Go (.go)
- [ ] Rust (.rs)

#### 3.2.3 Similarity Detection Algorithms
- [ ] **Token-based comparison** (basic)
- [ ] **AST (Abstract Syntax Tree) comparison** (advanced)
- [ ] **N-gram comparison** (text similarity)
- [ ] **K-gram / Winnowing** (fingerprinting)

#### 3.2.4 Output Format
```json
{
  "job_id": "uuid",
  "status": "completed|processing|failed",
  "total_submissions": 30,
  "total_pairs": 435,
  "results": [
    {
      "submission_a": "student1",
      "submission_b": "student2",
      "similarity_score": 0.85,
      "matching_blocks": [
        {
          "file_a": "main.py",
          "file_b": "main.py",
          "lines_a": "10-50",
          "lines_b": "15-55",
          "similarity": 0.92
        }
      ]
    }
  ],
  "threshold": 0.7,
  "execution_time_ms": 12500
}
```

---

## 4. API Specification

### 4.1 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/jobs` | Create new similarity analysis job |
| GET | `/api/v1/jobs/{job_id}` | Get job status |
| GET | `/api/v1/jobs/{job_id}/results` | Get similarity results |
| DELETE | `/api/v1/jobs/{job_id}` | Cancel/delete job |
| GET | `/api/v1/languages` | List supported languages |
| POST | `/api/v1/jobs/{job_id}/abort` | Abort running job |

### 4.2 Create Job Request
```json
{
  "name": "Assignment 1 - Sorting Algorithms",
  "threshold": 0.7,
  "languages": ["python", "java"],
  "exclude_patterns": ["__pycache__", "*.class", "node_modules"]
}
```

### 4.3 Upload Submission
- Multipart form upload
- ZIP file containing submissions
- Each student in separate folder

---

## 5. Technical Architecture

### 5.1 Tech Stack
- **Language:** Python 3.11+
- **Framework:** FastAPI (async REST API)
- **Database:** [TBD - SQLite for small, PostgreSQL for production]
- **Caching:** Redis (optional)
- **Queue:** Celery or similar for background tasks

### 5.2 Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `api/` | REST endpoints, request validation |
| `core/parser/` | Parse code files by language |
| `core/processor/` | Tokenize, normalize code |
| `core/similarity/` | Similarity algorithms |
| `core/analyzer/` | Orchestrate analysis pipeline |
| `models/` | Pydantic schemas for data |
| `config/` | Configuration management |

---

## 6. Non-Functional Requirements

### 6.1 Performance
- Process 100 submissions (< 100 files each) in < 30 seconds
- Async processing for concurrent jobs
- Timeout per job: 5 minutes (configurable)

### 6.2 Scalability
- Horizontal scaling via queue workers
- Stateless API design

### 6.3 Security
- No execution of uploaded code
- File size limits
- Path traversal prevention
- Rate limiting: 10 requests/minute per client

### 6.4 Reliability
- Graceful error handling
- Retry failed jobs (max 3 attempts)
- Job persistence (survive restart)

---

## 7. Configuration Options

```yaml
# config/default.yaml
service:
  host: "0.0.0.0"
  port: 8000
  debug: false

analysis:
  default_threshold: 0.7
  max_file_size_mb: 5
  max_folder_size_mb: 100
  job_timeout_seconds: 300
  max_concurrent_jobs: 10

languages:
  supported:
    - python
    - java
    - javascript
    - c
    - cpp
  exclude_patterns:
    - "__pycache__"
    - "*.class"
    - "node_modules"
    - ".git"

algorithms:
  enabled:
    - token
    - ngram
  default: "token"

storage:
  type: "local"  # or "s3"
  path: "./data/submissions"
```

---

## 8. Open Questions / TBD

| Item | Question | Status |
|------|----------|--------|
| Q1 | Should we support binary file comparison? | Open |
| Q2 | Storage for old jobs - TTL? | Open |
| Q3 | Authentication mechanism? | Open |
| Q4 | Multi-tenancy support? | Open |
| Q5 | Similarity report persistence? | Open |
| Q6 | Incremental analysis (new submissions)? | Open |

---

## 9. Out of Scope (v1.0)

- User interface / Web UI
- User authentication
- Payment / Billing
- Email notifications
- Visualization of similarity results
- Direct student access

---

## 10. Success Criteria

- [ ] Upload ZIP folder with 50+ submissions
- [ ] Return similarity scores for all pairs in < 30 seconds
- [ ] Correctly identify obvious copies (same code with variable renaming)
- [ ] API response matches documented schema
- [ ] 80%+ unit test coverage on core algorithms

---

## 11. TODO

- [ ] Finalize supported languages list
- [ ] Choose database solution
- [ ] Define authentication approach
- [ ] Set storage TTL policy
- [ ] Review and approve PRD

---

*Document Status: Draft*  
*Last Updated: 2026-03-27*
