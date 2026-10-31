# Judge Protocol v1

**Status:** implemented for the pull-based control-plane core; real sandbox execution is Plan B.  
**Base URL:** `/api/v1/judge/`  
**Auth:** `Authorization: Bearer <judge-token>` on every request. The server stores only the SHA-256 of the token. Blocked judges receive `403`.

The worker is a client: it polls for work, claims one job with a lease, downloads the immutable test package, executes it, and posts results. The server never runs user code.

## Worker lifecycle

1. `POST /register` with protocol version and capabilities.
2. `POST /heartbeat` every 10 seconds.
3. `POST /jobs/claim` with supported language keys.
4. `POST /jobs/{id}/start` after claiming.
5. `POST /jobs/{id}/cases` with per-case results (idempotent).
6. `POST /jobs/{id}/finish` or `POST /jobs/{id}/fail`.
7. Repeat from claim.

Claim is non-blocking in v1. `wait_seconds` is accepted but ignored; a `204` means no eligible job. The worker should poll with a short delay.

## Endpoints

### `POST /register`

```json
{
  "protocol_version": 1,
  "capabilities": {
    "languages": ["PY3", "CPP17"],
    "sandbox": "go-judge"
  }
}
```

Response:

```json
{"judge_id": 1, "heartbeat_interval": 10}
```

### `POST /heartbeat`

```json
{"load": 0.35, "running_jobs": 1, "cached_packages": ["<sha256>"]}
```

Response:

```json
{"ok": true, "next_heartbeat": 10}
```

### `POST /jobs/claim`

```json
{"languages": ["PY3", "CPP17"], "max_jobs": 1, "wait_seconds": 0}
```

`max_jobs` is reserved for a later batch extension; v1 claims at most one job.

Response `200`:

```json
{
  "job_id": 101,
  "submission_id": 55,
  "language": "PY3",
  "source": "print(1)",
  "limits": {"time": 2.0, "memory": 262144},
  "short_circuit": false,
  "partial_score": false,
  "contest_points": 100.0,
  "package": {
    "problem_id": 7,
    "sha256": "<sha256>",
    "url": "/api/v1/judge/packages/7?sha256=<sha256>"
  },
  "checker": {"type": "exact"},
  "cases": [
    {"id": "1", "input": "data/01.in", "answer": "data/01.ans", "points": 50, "group": "default"}
  ],
  "groups": [{"id": "default", "points": 100, "mode": "sum"}],
  "lease_seconds": 60
}
```

Response `204`: no eligible job; do not retry in a tight loop.

### `POST /jobs/{job_id}/start`

Empty JSON body. Marks the job `running`, sets the submission to `JG`, and extends the lease.

### `POST /jobs/{job_id}/cases`

```json
{
  "package_sha256": "<sha256 from claim>",
  "cases": [
    {
      "case_number": 1,
      "status": "AC",
      "time_used": 0.05,
      "memory_used": 1024,
      "points": 50,
      "total_points": 50,
      "feedback": "",
      "output": ""
    }
  ]
}
```

Results are upserted by `(submission, case_number)`. Posting the same case twice is safe. The server updates case counters and emits `submission.case`; it does not finalize the verdict. Workers should send `package_sha256`; a mismatch is rejected with `409` so results from stale test data cannot be applied.

### `POST /jobs/{job_id}/finish`

```json
{
  "package_sha256": "<sha256 from claim>",
  "status": "completed",
  "result": "AC",
  "points": 100,
  "time_used": 0.12,
  "memory_used": 2048,
  "case_total": 2,
  "case_passed": 2,
  "error_message": ""
}
```

The server ignores worker-supplied `points`, `time_used`, and `memory_used`; it recomputes them from persisted case rows and the immutable package manifest. Calling `finish` twice is idempotent and returns the same final submission.

### `POST /jobs/{job_id}/fail`

```json
{"status": "error", "result": "CE", "error_message": "compiler output"}
```

Marks the submission `ER` with the supplied valid result code (`CE` or `IE` fallback) and marks the job failed.

### `GET /packages/{problem_id}?sha256=<hash>`

Returns the ZIP archive for the exact package hash. A package can still be downloaded after it stops being the active version, so queued jobs cannot get stuck. The worker must verify the SHA-256 before extracting.

## Lease and retry

- Claim duration: **60 seconds**.
- Worker heartbeat/lease extension: every **10 seconds**.
- Expired `claimed`/`running` jobs are requeued while `attempts < max_attempts` (default **3**).
- After the attempt limit, the job is marked `failed` and the submission becomes `ER/IE`.
- `start`/`cases`/`finish`/`fail` reject expired or foreign jobs with `409`/`403`.
- Use row locks (`select_for_update(skip_locked=True)`) when claiming; two workers must never receive the same job.

## Package manifest

The package archive is content-addressed by SHA-256 and contains `manifest.json` plus case files:

```json
{
  "schema": 1,
  "problem_code": "aplusb",
  "time_limit": 2.0,
  "memory_limit": 262144,
  "partial_score": false,
  "short_circuit": false,
  "checker": {"type": "exact"},
  "cases": [
    {
      "id": "1",
      "input": "data/01.in",
      "answer": "data/01.ans",
      "input_sha256": "<sha256>",
      "answer_sha256": "<sha256>",
      "points": 100,
      "group": "default"
    }
  ],
  "groups": [{"id": "default", "points": 100, "mode": "sum"}]
}
```

Group modes are `sum` and `min`; group scores are capped at the group's points. `partial_score=false` means any non-AC case yields `WA` with zero points; `partial_score=true` enables `PT` and subtask scores. The checker field is carried for the real worker; v1's fake-worker tests use exact comparison and server scoring.

## Status codes

| Code | Meaning |
|---|---|
| 200 | Accepted |
| 204 | No job available |
| 401 | Missing/invalid judge token |
| 403 | Blocked judge or job owned by another judge |
| 404 | Unknown job or package |
| 409 | Job not active, lease expired, or state conflict |
| 422 | Invalid payload |

Errors use the shared JSON shape `{"error": "...", "code": "..."}`.

## Security

- Use TLS in production; never send a judge token over plain HTTP.
- Tokens are per-judge, hashed at rest, and should be rotated.
- Judge tokens are separate from user JWT/session auth.
- Package hashes prevent grading against stale or substituted test data.
- The real worker must run code in a sandbox with CPU, memory, filesystem, and network limits; the control plane never executes user code.

## Reference implementation and tests

- Fake-worker end-to-end test: `tests/test_judge_e2e.py`
- Gateway/auth/lease tests: `tests/test_judge_gateway.py`
- Server scoring tests: `tests/test_judge_core.py`
