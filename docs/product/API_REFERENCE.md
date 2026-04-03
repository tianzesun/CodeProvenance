# API Reference: IntegrityDesk REST Interface

> **A Comprehensive Guide to Programmatic Analysis and Integration**

IntegrityDesk provides a professional REST API for seamless integration with Learning Management Systems (LMS), CI/CD pipelines, and custom administrative tools.

---

## 1. Authentication

All requests must include a valid API key in the request header:
`Authorization: Bearer <YOUR_API_KEY>`

---

## 2. Core Endpoints

### 2.1 Submit for Analysis
`POST /api/v1/analyze`

**Request Body** (Multipart/Form-Data):
- `files`: One or more code files or a ZIP archive.
- `metadata`: Optional JSON metadata (e.g., assignment ID, student ID).
- `config`: Optional engine configuration (thresholds, weights).

**Response** (JSON):
- `submission_id`: Unique identifier for the job.
- `status`: `pending`, `in_progress`, `completed`, `failed`.
- `estimated_time`: Approximate time to completion.

---

### 2.2 Retrieve Results
`GET /api/v1/results/{submission_id}`

**Response** (JSON):
- `score`: Composite similarity index (0.0-1.0).
- `agreement_index`: Statistical consensus between engines.
- `uncertainty`: Uncertainty margin (e.g., ±0.03).
- `findings`: Array of detailed engine-specific evidence.
- `explanations`: Array of forensic insights (e.g., "Stylometry Match").

---

### 2.3 Download Forensic Report
`GET /api/v1/report/{submission_id}`

**Parameters**:
- `format`: `html` (default), `pdf`, `json`.

**Response**:
The requested forensic report file.

---

## 3. Webhooks & Events

IntegrityDesk can notify your system when an analysis is complete.

### 3.1 Register Webhook
`POST /api/v1/webhooks`

**Request Body**:
- `url`: The endpoint to receive the notification.
- `events`: List of events to subscribe to (e.g., `analysis.complete`, `analysis.failed`).

### 3.2 Event Payload Example
```json
{
  "event": "analysis.complete",
  "submission_id": "uuid-1234",
  "composite_score": 0.88,
  "agreement_index": 0.92,
  "high_risk": true,
  "report_url": "https://api.integritydesk.io/v1/report/uuid-1234"
}
```

---

## 4. LMS Integrations (LTI Support)

IntegrityDesk supports standard LTI 1.3 for integration with:
- **Canvas**
- **Moodle**
- **Blackboard**
- **Brightspace**

*Please contact your institutional IT department for integration keys and setup.*

---

## 5. Rate Limits & Usage

Usage is monitored per API key:
- **Free Tier**: 10 requests/min, 50 submissions/month.
- **Pro Tier**: 100 requests/min, 10,000 submissions/month.
- **Enterprise**: Custom limits based on institutional needs.

---
**IntegrityDesk Developer Platform**
*Built for Scale. Engineered for Truth.*
