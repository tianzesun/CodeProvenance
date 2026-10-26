# API Reference: public REST API

The programmatic API for submitting code and reading similarity results. It is
implemented in `src/backend/api/routes/analyze.py` and mounted under `/api` in
`src/backend/api/server.py`. Submissions go through the same background
pipeline as the web upload flow.

Last checked against the code: 2026-10-26.

## Authentication

Every request needs a workspace API key in the `X-API-Key` header. A request
without one gets `401` with `WWW-Authenticate: ApiKey`. All results are scoped
to the key's workspace: a job from another workspace returns `404`.

```
X-API-Key: <workspace API key>
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/analyze` | Submit two or more files for comparison |
| `GET` | `/api/v1/jobs/{job_id}` | Job status, plus results once completed |
| `GET` | `/api/v1/jobs/{job_id}/results` | Paged similarity results |
| `GET` | `/api/v1/jobs/{job_id}/report` | Report link for a completed job |
| `GET` | `/api/v1/usage` | Job and result counts for the workspace |

### `POST /api/v1/analyze`

JSON body:

| Field | Required | Notes |
| --- | --- | --- |
| `submissions` | yes | 2–500 objects `{ "name", "content", "language"? }`. `content` is a string of at most 1,000,000 characters. |
| `name` | no | Job name; defaults to `Unnamed Analysis`. |
| `threshold` | no | Number in `[0, 1]`; default `0.2`. |
| `assignment_id` | no | Links the job to an existing assignment. |
| `options` | no | Object. Only `assignment_mode` is read today. |
| `webhook_url` | no | Must be a public `https` URL. Stored on the job, but completion webhooks currently go to the workspace's `WEBHOOK_URL` setting instead (see below). |

File names are reduced to a single safe path component, made unique within
the job, and given a `.py` extension when the extension is not a recognized
code type. All validation runs before anything is written, so a `400` never
leaves a partial job behind.

```json
{
  "name": "CS101 Assignment 3",
  "submissions": [
    { "name": "student1_solution.py", "content": "def fibonacci(n): ..." },
    { "name": "student2_solution.py", "content": "def fib(n): ..." }
  ],
  "threshold": 0.2
}
```

Response `201`:

```json
{
  "job_id": "…",
  "status": "queued",
  "status_url": "/api/v1/jobs/…",
  "estimated_completion": "2026-10-26T15:04:05+00:00",
  "submission_count": 2,
  "submission_ids": ["…", "…"],
  "message": "Analysis job created with 2 submissions"
}
```

`estimated_completion` is a rough guess (about 2 seconds per pair, minimum
10 seconds), not a promise.

### `GET /api/v1/jobs/{job_id}`

Query: `include_results` (default `true`; set `false` when polling).

Returns `job_id`, `name`, `status`, `progress`, `submission_count`,
`threshold`, `created_at`, `started_at`, `completed_at`, `error_message` and
`results`. `progress` is `100` when completed and `0` otherwise; there is no
finer-grained progress. Once completed, `results` holds up to 1,000 pairs,
each with `submission_a_id`, `submission_b_id`, `similarity_score`,
`confidence_lower` and `confidence_upper`.

### `GET /api/v1/jobs/{job_id}/results`

Query: `threshold` (`0`–`1`, optional), `limit` (1–5000, default 1000),
`offset` (default 0). Returns `409` until the job is completed.

Each item has `submission_a` and `submission_b` (`id`, `name`),
`similarity_score`, `confidence_interval` (`lower`, `upper`, `confidence`) and
`matching_blocks`.

### `GET /api/v1/jobs/{job_id}/report`

Query: `format` = `html` (default), `pdf` or `json`. Returns `409` until the
job is completed.

Not finished: this returns a `report_url` of the form
`/api/v1/jobs/{job_id}/report/download?format=…`, but no route serves that
path yet.

### `GET /api/v1/usage`

Returns `jobs_created`, `files_analyzed` (the number of stored result pairs),
`api_calls` (the sum of the two) and a `rate_limit` block. The `rate_limit`
figures are fixed values, not live counters.

## Rate limits

`POST /api/v1/analyze` is rate limited per workspace: 60 requests a minute,
1,000 an hour and 10,000 a day by default. The `GET` endpoints are not rate
limited by this router.

## Completion webhooks

When a job finishes (`completed` or `failed`), the server POSTs to the
workspace's `WEBHOOK_URL` setting, if one is set. The URL must be public
`https`, and its host is resolved again at send time to block private
addresses.

The payload carries no student names, file names or code:

```json
{
  "event": "analysis.completed",
  "job_id": "…",
  "status": "completed",
  "course": "…",
  "assignment": "…",
  "submissions": 2,
  "pairs_compared": 1,
  "pairs_flagged": 0,
  "results_url": "https://<frontend>/results/…",
  "finished_at": "…"
}
```

Headers: `X-IntegrityDesk-Event`, `X-IntegrityDesk-Timestamp` and, when the
server has `WEBHOOK_SECRET_KEY` set, `X-IntegrityDesk-Signature`. The
signature is `sha256=<hex HMAC-SHA256 of "<timestamp>.<body>">`. A failed
delivery is logged and does not affect the job.

## Errors

`400` for invalid input (the message names the field), `401` without a valid
key, `404` for an unknown job or one outside the workspace, `409` when results
or a report are requested before the job completes. A storage failure returns
`500` with a generic message and a reference ID that matches the server log.
