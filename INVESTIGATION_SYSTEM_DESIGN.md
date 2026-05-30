# IntegrityDesk: Academic Investigation & Evidence Management System
## Dean-Grade Architecture Design

---

## 1. SYSTEM OVERVIEW

### Mission
Transform IntegrityDesk from a "Detection Engine" into a complete **Academic Investigation & Evidence Management System** suitable for formal disciplinary workflows.

### Core Principle
The system produces **evidence bundles**, not verdicts. Final decisions are made by humans (professors, committees) using evidence as input.

---

## 2. ARCHITECTURE PRINCIPLES

### 2.1 NO AUTOMATIC ACCUSATION
The system must NEVER output:
- "This student cheated"
- "AI generated submission"
- "Plagiarism confirmed"

Permitted outputs:
- `CLEAN` - No significant similarity detected
- `REVIEW REQUIRED` - Evidence suggests examination needed
- `STRONG SIMILARITY OBSERVED` - High confidence evidence of shared work

### 2.2 EVIDENCE-FIRST ARCHITECTURE
All outputs are structured evidence bundles that can be:
- Audited by third parties
- Reproduced by independent reviewers
- Explained in academic hearings

### 2.3 ROLE-BASED ACCESS CONTROL
- **Professors**: Create cases, review evidence, assign investigations
- **Course Coordinators**: Oversee multiple instructors
- **Department Chairs**: Review escalated cases
- **Associate Deans**: Final academic integrity decisions
- **Committees**: Multi-stakeholder review panels

---

## 3. DATA MODEL

### 3.1 Core Entities

```
Organization (Institution)
├── Course
│   └── Assignment
│       └── Job (Analysis Batch)
│           ├── Submission
│           └── SimilarityResult
├── Case (Investigation)
│   ├── CaseResultLink
│   ├── CaseComment
│   └── Report
└── User (Professor, Student, Admin)
```

### 3.2 Evidence Bundle Schema

```json
{
  "case_id": "uuid",
  "submission_pair_id": "uuid",
  "timestamp": "iso-datetime",
  
  "structural_evidence": {
    "shape_similarity": {"score": 0.0-1.0, "explanation": "..."},
    "function_structure": {"match_count": N, "details": "..."},
    "divergence_score": 0.0-1.0
  },
  
  "lexical_evidence": {
    "ngram_match": {"score": 0.0-1.0, "matched_spans": [...]},
    "winnowing_match": {"score": 0.0-1.0, "fingerprints": [...]},
    "token_overlap": {"score": 0.0-1.0, "common_tokens": [...]}
  },
  
  "semantic_evidence": {
    "embedding_similarity": {"score": 0.0-1.0, "confidence": "..."},
    "semantic_spans": [{"start": N, "end": N, "semantic_type": "..."}]
  },
  
  "control_flow_evidence": {
    "if_structure": {"match": true, "details": "..."},
    "loop_structure": {"match": true, "details": "..."},
    "branching_patterns": {"score": 0.0-1.0}
  },
  
  "historical_evidence": {
    "style_consistency": {"student_history": "...", "current_submission": "..."},
    "past_similarity": [{"assignment_id": "...", "score": ...}]
  },
  
  "cluster_evidence": {
    "cluster_id": "uuid",
    "cluster_size": N,
    "cluster_members": ["submission_id", ...],
    "cluster_similarity": 0.0-1.0
  },
  
  "ai_indicators": {
    "perplexity_score": 0.0-1.0,
    "uncertainty_metrics": {...},
    "NOTE": "Non-decisive indicator only"
  }
}
```

---

## 4. INVESTIGATION WORKFLOW

### 4.1 Phase 1: Submission & Analysis
```
1. Instructor uploads submissions
2. System creates Job → Assignment → Course hierarchy
3. Automated analysis runs all engines
4. SimilarityResults created with verdicts:
   - CLEAN (score < threshold)
   - REVIEW REQUIRED (threshold <= score < high_threshold)
   - STRONG SIMILARITY (score >= high_threshold)
```

### 4.2 Phase 2: Case Creation
```
1. Instructor reviews results
2. Creates Case for suspicious submissions
3. Assigns to investigator (self or delegate)
4. System auto-links SimilarityResults to Case
```

### 4.3 Phase 3: Evidence Review
```
1. Investigator opens Case
2. Reviews evidence bundles
3. Adds notes/comments
4. Can request additional analysis
```

### 4.4 Phase 4: Escalation
```
1. Case status: UNDER_REVIEW → ESCALATED
2. Assigned to Department Chair
3. Committee formed if needed
4. Additional evidence gathered
```

### 4.5 Phase 5: Resolution
```
1. Committee reviews all evidence
2. Final determination made
3. Report generated
4. Case closed
```

---

## 5. API ENDPOINTS

### 5.1 Cases
```
POST   /api/cases                    # Create new case
GET    /api/cases                    # List cases (with filters)
GET    /api/cases/{id}               # Get case details
PUT    /api/cases/{id}               # Update case (status, notes)
POST   /api/cases/{id}/comments      # Add comment
POST   /api/cases/{id}/reports       # Generate report
DELETE /api/cases/{id}               # Close/archive case
```

### 5.2 Evidence
```
GET  /api/cases/{id}/evidence        # Get evidence bundle
GET  /api/evidence/{id}              # Get specific evidence
POST /api/evidence/compare            # Manual re-comparison
```

### 5.3 Clusters
```
GET  /api/clusters                   # List all clusters
GET  /api/clusters/{id}              # Get cluster details
POST /api/clusters/analyze            # Trigger cluster analysis
```

### 5.4 Reports
```
POST   /api/reports                  # Generate new report
GET    /api/reports                  # List reports
GET    /api/reports/{id}             # Get report
GET    /api/reports/{id}/download    # Download PDF/HTML
```

---

## 6. FRONTEND DASHBOARD STRUCTURE

### 6.1 Case Queue
```
Filters:
- Status: OPEN, UNDER_REVIEW, ESCALATED, CLOSED
- Course/Assignment
- Priority: LOW, MEDIUM, HIGH, URGENT
- Date range

Columns:
- Case ID | Title | Course | Students | Status | Priority | Created | Actions
```

### 6.2 Case Detail View
```
┌─────────────────────────────────────────────────────────────┐
│ CASE: CS101 - Assignment 3 - John Doe                       │
├─────────────────────────────────────────────────────────────┤
│ STATUS: UNDER REVIEW     INVESTIGATOR: Prof. Smith         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ EVIDENCE SUMMARY ───────────────────────────────────┐  │
│  │ Structural:    ████████░░ 80%                        │  │
│  │ Lexical:       ██████████ 100%                       │  │
│  │ Semantic:      ██████░░░░ 60%                        │  │
│  │ Control Flow:  ██████████ 100%                       │  │
│  │ Divergence:    ██░░░░░░░░ 20%                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ SUBMISSION PAIR ─────────────────────────────────────┐  │
│  │ File A: student_john.py    File B: student_jane.py   │  │
│  │ Size: 2.4KB              Size: 2.3KB                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ ACTIONS ─────────────────────────────────────────────┐  │
│  │ [View Detailed Evidence] [Request Re-analysis]        │  │
│  │ [Add Note] [Escalate] [Generate Report]               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ TIMELINE ─────────────────────────────────────────────┐  │
│  │ 2024-01-15: Case created by Prof. Smith               │  │
│  │ 2024-01-16: Evidence reviewed                         │  │
│  │ 2024-01-17: Additional analysis requested             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─ COMMENTS ────────────────────────────────────────────┐  │
│  │ Prof. Smith: "Similar structure but different logic"  │  │
│  │                                                       │  │
│  │ [Add Comment...]                                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Evidence Viewer
```
Side-by-side code comparison with:
- Matched spans highlighted
- AST visualization
- Control flow graph
- Token alignment

Evidence breakdown:
- Structural evidence with explanations
- Lexical matches with context
- Semantic clusters
- Historical context
```

### 6.4 Cluster Graph
```
Force-directed graph visualization:
- Nodes: Submissions
- Edges: Similarity scores
- Color coding: By student, by time, by cluster

Click node → show evidence details
Click edge → show pair comparison
```

---

## 7. REPORT GENERATION SYSTEM

### 7.1 Report Structure (Dean-Ready)

```
1. EXECUTIVE SUMMARY
   - Case overview
   - Key findings
   - Recommendation

2. EVIDENCE OVERVIEW
   - Summary of all evidence types
   - Confidence levels
   - Timeline of analysis

3. STRUCTURAL ANALYSIS
   - AST shape comparison
   - Function structure analysis
   - Divergence metrics

4. LEXICAL ANALYSIS
   - N-gram matching results
   - Token overlap analysis
   - Fingerprint similarities

5. SEMANTIC ANALYSIS
   - Embedding similarity
   - Semantic cluster analysis
   - Natural language explanations

6. CONTROL FLOW ANALYSIS
   - Branching structure comparison
   - Loop pattern matching
   - Conditional logic analysis

7. HISTORICAL CONTEXT
   - Student's past submissions
   - Style evolution
   - Previous similarity incidents

8. CLUSTER CONTEXT
   - Collaboration network analysis
   - Group similarity patterns
   - Peer comparison

9. DIVERGENCE ANALYSIS
   - Structural differences
   - Logic variations
   - Key distinguishing features

10. REVIEWER NOTES
    - Instructor comments
    - Investigator findings
    - Committee deliberations

11. RECOMMENDATION
    - Based on evidence threshold
    - Academic policy alignment
    - Next steps
```

### 7.2 Language Policy

**Approved Terminology:**
- "Structural similarity observed"
- "Lexical overlap detected"
- "Semantic patterns align"
- "Control flow structures match"
- "Evidence suggests shared work"
- "Review recommended"

**Prohibited Terminology:**
- "Plagiarism" (unless formally determined)
- "Cheating" (unless formally determined)
- "AI-generated" (unless formally determined)
- "Copy" or "copied" (use "shared elements")

---

## 8. DEPLOYMENT ARCHITECTURE

### 8.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Load Balancer                                │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│   Web Tier    │       │  API Gateway  │       │  Web Tier     │
│  (Next.js)    │       │   (FastAPI)   │       │  (Next.js)    │
└───────────────┘       └───────────────┘       └───────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│  Application  │       │  Application  │       │  Application  │
│   Services    │       │   Services    │       │   Services    │
│ (Cases, etc.) │       │(Detection,    │       │(Reporting,   │
│               │       │ Evidence,     │       │  etc.)        │
│               │       │  Analysis)    │       │               │
└───────────────┘       └───────────────┘       └───────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │     PostgreSQL        │
                    │   (Primary DB)        │
                    └───────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│   GPU Pool    │       │   Redis Cache │       │  File Storage │
│ (Embedding    │       │               │       │ (S3/MinIO)    │
│  Analysis)    │       │               │       │               │
└───────────────┘       └───────────────┘       └───────────────┘
```

### 8.2 Scalability Considerations

- **Horizontal scaling**: API gateway + load balancer
- **Database read replicas**: For case listing queries
- **GPU pool**: Dedicated workers for embedding analysis
- **Redis caching**: Frequently accessed evidence bundles
- **File storage**: S3-compatible for submission files

---

## 9. SECURITY & COMPLIANCE

### 9.1 Data Protection
- Student data encrypted at rest
- TLS for all communications
- Role-based access control
- Audit logging for all actions

### 9.2 Legal Safeguards
- Evidence chain of custody
- Immutable audit logs
- Report versioning
- Non-repudiation timestamps

---

## 10. IMPLEMENTATION ROADMAP

### Phase 1: Core Investigation System (Already Started)
- [x] Evidence extraction architecture
- [x] Case management models
- [x] Timeline events
- [ ] Evidence bundle API
- [ ] Case workflow API
- [ ] Report generation

### Phase 2: Investigation UI
- [ ] Case dashboard
- [ ] Evidence viewer
- [ ] Cluster visualization
- [ ] Report preview

### Phase 3: Advanced Features
- [ ] Committee workflow
- [ ] Escalation management
- [ ] Multi-institution support
- [ ] Integration APIs

---

## 11. KEY DIFFERENCES FROM TRADITIONAL SYSTEMS

| Aspect | Traditional MOSS/JPlag | IntegrityDesk Dean-Grade |
|--------|------------------------|--------------------------|
| Output | Similarity scores | Evidence bundles |
| Decisions | Automated | Human-in-the-loop |
| Language | Technical | Academic/policy |
| Audit Trail | Minimal | Full timeline |
| Report | Simple text | Structured formal |
| Scale | Class-level | Institution-level |

---

## 12. SUCCESS METRICS

### 12.1 Academic Workflow Metrics
- Time from submission to case resolution
- Instructor satisfaction with evidence clarity
- Committee acceptance rate of reports
- Reduction in appeal requests

### 12.2 Technical Metrics
- Evidence bundle generation time
- Report generation accuracy
- Audit log completeness
- System uptime

---

This architecture transforms IntegrityDesk into a production-ready Academic Investigation & Evidence Management System suitable for university-wide deployment and formal academic disciplinary proceedings.