[🏠 Project README](../../README.md) · [📚 Documentation](../README.md) · [← Testing](../development/testing.md) · [Next: Package format →](package-format.md)

# 📡 API reference

JudgeLoom exposes a typed Django Ninja API. The generated schema is the
authoritative field-level reference; this page is the map.

| Resource | URL |
| :--- | :--- |
| API root | `https://<host>/api/` |
| Swagger UI | `https://<host>/api/docs` |
| OpenAPI JSON | `https://<host>/api/openapi.json` |
| Liveness | `https://<host>/api/health/live` |
| Readiness | `https://<host>/api/health/ready` |
| Judge gateway | `https://<host>/api/v1/judge/` |

> [!TIP]
> Use `/api/docs` while developing. The judge worker uses the separate
> `/api/v1/judge/` gateway documented in [Protocol v1](../judge/protocol-v1.md).

---

## 🔐 Authentication

### Register

```http
POST /api/accounts/register
Content-Type: application/json

{"username":"alice","email":"alice@example.com","password":"..."}
```

### Log in (JWT)

```http
POST /api/accounts/login
Content-Type: application/json

{"username_or_email":"alice","password":"..."}
```

Response:

```json
{"access_token":"<jwt>","token_type":"Bearer"}
```

Send protected requests with:

```http
Authorization: Bearer <jwt>
```

Sessions are also accepted by browser-facing endpoints. Judge workers use a
separate per-judge bearer token, never a user JWT.

---

## 🗺️ Endpoint map

| Area | Routes | Notes |
| :--- | :--- | :--- |
| Accounts | `/api/accounts/register`, `/login`, `/refresh`, `/me`, `/logout` | JWT/session |
| Problems | `/api/problems/`, `/{code}`, `/{code}/statistics`, `/{code}/solutions` | Visibility enforced |
| Submissions | `/api/submissions/`, `/run`, `/{id}`, `/{id}/source`, `/{id}/test-cases`, `/{id}/share`, `/{id}/shadow`, `/{id}/rejudge` | Owner/staff scoped |
| Contests | `/api/contests/`, `/{key}`, `/{key}/submissions` | Participation enforced |
| Tags | `/api/tags/`, `/{code}` | Visible-problem counts |
| Content | `/api/content/posts`, `/navigation`, comments | Staff authoring / visibility |
| Tickets | `/api/tickets/` | Link visibility enforced |
| Ratings | `/api/ratings/` | Rating history/changes |
| Judge admin | `/api/judge/languages`, `/judges`, `/metrics` | Staff/admin |
| Judge gateway | `/api/v1/judge/register`, `/heartbeat`, `/jobs/claim`, ... | Worker only |
| Health | `/api/health/live`, `/api/health/ready` | Public probes |

See Swagger for exact request/response models and query parameters.

---

## 📝 Submit a solution

```bash
curl -s -X POST https://<host>/api/submissions/ \
  -H "Authorization: Bearer $JWT" \
  -H 'Content-Type: application/json' \
  -d '{
    "problem_code": "aplusb",
    "language_id": 5,
    "source_code": "a, b = map(int, input().split())\nprint(a + b)\n"
  }'
```

Get language ids from `GET /api/judge/languages` (public).

Custom-input run:

```http
POST /api/submissions/run
```

The run mode accepts `stdin` and optional `expected_output`; it does not award
points or update user statistics.

---

## 📊 Submission states

| Status | Meaning |
| :--- | :--- |
| `Q` | Queued |
| `JG` | Being judged |
| `CM` | Completed |
| `ER` | Error |

| Result | Meaning |
| :--- | :--- |
| `AC` | Accepted |
| `WA` | Wrong answer |
| `TLE` | Time limit exceeded |
| `MLE` | Memory limit exceeded |
| `RTE` | Runtime error |
| `CE` | Compile error |
| `PE` | Presentation error |
| `PT` | Partial score |
| `IE` | Internal error |

Per-case results are exposed to authorized owners/staff; public metadata never
includes source code or test output.

---

## 📡 WebSocket updates

Live submission and contest feeds use Django Channels. Browser clients
authenticate with the normal session/JWT flow; tokens are revalidated on
revocation/ban. See the source consumers under `apps/*/consumers.py`.

---

## 🧾 Error format

Control-plane errors use the shared JSON shape:

```json
{"detail": "Human-readable message"}
```

Judge gateway errors use:

```json
{"error": "Human-readable message", "code": "machine_code"}
```

Always check the HTTP status: `400/422` validation, `401` auth, `403`
permission, `404` unknown, `409` state/lease conflict.

---

## 🔗 Related documentation

- [Judge protocol v1](../judge/protocol-v1.md)
- [Package format](package-format.md)
- [Configuration](../getting-started/configuration.md)
- [Security model](../architecture/security.md)

---

<div align="center">
  <sub>← <a href="../development/testing.md">Testing</a> · <a href="../README.md">Documentation hub</a> · <a href="package-format.md">Package format</a> →</sub>
</div>
