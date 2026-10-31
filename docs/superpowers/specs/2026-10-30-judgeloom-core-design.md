# JudgeLoom Core — Design

**Ngày:** 2026-10-30  
**Trạng thái:** Draft chờ duyệt  
**Phạm vi:** backend core, API-first, open-source quốc tế, chấm batch (stdin/stdout) trước; LeetCode-style là adapter sau.  
**Research nền:** [`docs/research/open-source-online-judges.md`](../../research/open-source-online-judges.md)

---

## 1. Mục tiêu và lý do

JudgeLoom là backend online judge mã nguồn mở, có thể self-host, cung cấp API cho nhiều frontend. Mục tiêu gần nhất không phải làm một LeetCode hoàn chỉnh, mà là **một lõi chấm bài đáng tin cậy**:

1. Người dùng nộp source code qua API.
2. Hệ thống lưu submission, đưa vào hàng đợi, giao cho judge worker.
3. Worker chạy code trong sandbox, chấm từng test case, trả kết quả.
4. API và WebSocket cập nhật trạng thái realtime.
5. Contest có ranking/freeze/rating đúng.
6. Người khác có thể tự triển khai bằng Docker Compose, đóng góp code, và dùng API mà không phụ thuộc một frontend cụ thể.

Thành công của v1 được đo bằng một luồng cụ thể: **nộp một bài Python/C++ qua Swagger, worker thật chấm trong sandbox, trả AC/WA/TLE/CE, WebSocket hiện tiến trình, và kết quả nằm đúng trong DB/contest ranking.**

---

## 2. Hiện trạng và khoảng trống

### Đã có

- Django app cho accounts, problems, submissions, contests, judge, ratings, content, tickets, tags, organizations.
- API Ninja với khoảng 73 route.
- Service layer, custom exceptions, cache invalidation, Celery, Channels.
- Contest format registry (default, ICPC, IOI, AtCoder, ECOO).
- Test suite 109 test, factory_boy, Docker/CI cơ bản.

### Chưa có hoặc đang sai

| Vấn đề | Bằng chứng | Hệ quả |
|---|---|---|
| Không có migrations | Không có `apps/*/migrations/` | DB mới không có bảng; CI `makemigrations --check` fail |
| Judge bridge chỉ là in-memory registry | `BridgeManager` giữ handler trong process | Celery worker không thấy judge ở web process; submission nằm `Q` |
| Không có worker/sandbox | Không có transport, không có runner | Không chấm được bài thật |
| Test data không version/hash | `ProblemTestData` chỉ có ZIP + case filename | Worker không biết package nào là đúng; không cache/invalidate được |
| Contest scoring sai field | `_is_accepted` đọc `verdict`/`status`, không đọc `result`; `_submission_queryset` tìm `participation`, không phải `contest_participation` | ICPC/ECOO/AtCoder luôn 0 solved; ranking lẫn bài luyện |
| Freeze chỉ là che dữ liệu | `get_frozen_ranking` đổi `format_data` | Không phải freeze thật |
| Rating khởi tạo sai | `User.rating` default 0; `getattr(user, "rating", 1500)` không fallback | Contest rated đầu tiên tính từ 0 |
| Lifecycle task không chạy | Có task start/end/recalc nhưng không `.delay()`/schedule | Contest không tự start/end, rating không tự tính |
| Event bus không khớp consumer | `publish` gửi `event.broadcast` vào group `submissions`; consumer join `submission_{id}` | Realtime không hoạt động |
| Auth chia đôi | Login trả JWT; nhiều endpoint đọc session `request.user` | Client Bearer-only bị coi là anonymous |
| i18n chưa thật | Chỉ `en`/`vi`; thiếu `LocaleMiddleware` | Chưa sẵn sàng quốc tế |

---

## 3. Non-goals cho v1

- Không làm frontend trong repo này.
- Không làm billing/SaaS multi-tenant.
- Không tự viết sandbox ptrace/chroot.
- Không hỗ trợ interactive/communication/output-only trong v1 (để sau).
- Không hỗ trợ LeetCode function-call harness trong v1.
- Không tối ưu cho hàng triệu submission/ngày ngay từ đầu.

---

## 4. Quyết định kiến trúc

### D1 — Giữ Django làm control plane, pin Django 5.2 LTS

**Quyết định:** Django 5.2 LTS + Django Ninja + Pydantic v2 + PostgreSQL 16+ + Redis 7 + Celery 5 + Channels 4.  
**Lý do:** OJ web là CRUD/auth/contest/admin, không phải bottleneck. Django cho admin, ORM, auth, migrations, i18n, ecosystem và contributor pool. Django 5.2 LTS ổn định hơn feature release 6.0 cho một dự án open-source cần self-host lâu dài.  
**Hệ quả:** Đồng bộ README/pyproject/requirements; giữ CI Python 3.12; nếu một dependency bắt buộc 6.0 thì ghi exception rõ ràng.

### D2 — Judge worker là service Go riêng, v1 dùng go-judge

**Quyết định:** Worker viết bằng Go; execution backend của v1 là **go-judge** (MIT, HTTP/file cache, scale ngang). `isolate` chỉ là adapter post-v1/dev sau interface `Executor`; không nằm trong acceptance v1. Không chạy code người dùng trong Django/Celery process.  
**Lý do:** Một backend duy nhất giảm scope, tránh hai đường tích hợp và hai bộ privilege/cgroup requirements. Cần cô lập, giới hạn CPU/memory/FS/network, chạy nhiều language, và không để lỗi sandbox kéo sập web.  
**Hệ quả:** Worker là process riêng, user riêng, không root; chỉ chạy trên Linux (WSL/Docker cho dev Windows).

### D3 — Worker protocol pull-based qua HTTPS, có lease

**Quyết định:** Worker chủ động gọi API để `claim` job, `heartbeat`, tải package, gửi case/finish. Dùng long-poll để giảm latency; không dùng TCP push như DMOJ trong v1.  
**Lý do:** `BridgeManager` in-memory hiện tại không thể hoạt động đúng qua nhiều process. Pull model không cần inbound port, dễ qua NAT/firewall, dễ scale ngang, dễ test bằng HTTP, và có lease/retry rõ ràng. DOMjudge đã chứng minh mô hình judgehost pull.  
**Hệ quả:** Không cần bridge process giữ connection. Có thể thêm WebSocket push sau nếu latency là vấn đề; pull API vẫn là source of truth.

### D4 — Test data là content-addressed package

**Quyết định:** Mỗi problem có `ProblemPackage` bất biến, có `sha256`, manifest JSON, archive ZIP. Worker tải theo hash và cache; bridge chỉ dispatch khi worker có hash tương ứng hoặc cho phép tải.  
**Lý do:** Tránh worker chấm bằng test data cũ; hỗ trợ rejudge theo dataset; cho phép cache giữa nhiều worker.  
**Hệ quả:** API tải package riêng cho judge; object storage S3/MinIO cho production.

### D5 — Checker theo Testlib contract

**Quyết định:** Checker trả exit code theo Testlib: `0` OK, `1` WA, `2` PE, `3` fail, `5` points qua `quitp`.  
**Lý do:** Contract đơn giản, ổn định, được cộng đồng OJ dùng; tránh tự định nghĩa protocol checker.  
**Hệ quả:** Vendor `testlib.h` (MIT) kèm notice; hỗ trợ exact checker trước, custom checker sau.

### D6 — Contest: ICPC DMOJ, freeze DOMjudge, IOI subtask CMS

**Quyết định:** Sửa field names trước; ICPC dùng công thức DMOJ; freeze filter theo `submitted_at` như DOMjudge; IOI subtask score types theo CMS.  
**Lý do:** Đây là các implementation đã được chứng minh, tránh tự nghĩ lại format.  
**Hệ quả:** Ranking phải có public view và jury view; cache ranking theo `(contest, freeze_time, version)`.

### D7 — Rating: sửa Elo trước, Elo-MMR sau

**Quyết định:** v1 dùng Elo đã sửa (default 1500, exclusions, floor/ceiling); v2 port Elo-MMR từ DMOJ.  
**Lý do:** Rating không block chấm bài; sửa initial/exclusions là quick win; Elo-MMR cần thêm dữ liệu `mean`/`volatility`/`times_ranked`.
**Hệ quả:** Không giả volatility; lưu đủ dữ liệu để nâng cấp.

### D8 — Auth: JWT cho API, session cho admin, token riêng cho judge

**Quyết định:** Dùng `django-ninja-jwt` (hoặc equivalent đã kiểm chứng) cho access/refresh + blacklist; session cho Django admin; judge worker dùng token riêng đã hash, có rotation.  
**Lý do:** Một cơ chế auth thống nhất cho client; không trộn session/JWT tùy endpoint; judge không dùng JWT user.  
**Hệ quả:** Sửa toàn bộ router đọc `request.auth`; thêm scopes; OIDC/allauth sau.

### D9 — Event bus có contract tường minh

**Quyết định:** `publish(group, event_type, payload)`, gọi sau `transaction.on_commit`. Groups: `submission_{id}`, `contest_{key}`, `judge_{name}`. Types: `submission.status`, `submission.case`, `submission.finished`, `contest.ranking`, `contest.lifecycle`, `judge.status`.  
**Lý do:** Channels dispatch theo tên method; mọi mismatch hiện tại đều im lặng.  
**Hệ quả:** Consumer method names khớp type; test bằng `InMemoryChannelLayer` + `WebsocketCommunicator`.

### D10 — License: giữ AGPL-3.0-or-later + CLA

**Quyết định:** Giữ AGPL-3.0-or-later; thêm CLA từ đầu; dual-license sau nếu muốn bán SaaS. Không copy code Hydro (additional §7), HustOJ (GPL-2.0-only/mixed), Themis (closed). DMOJ/CMS (AGPL) được phép copy kèm notice; DOMjudge (GPL-2.0-or-later) chỉ học pattern hoặc integrate; go-judge/Testlib (MIT) được copy/integrate; Judge0/isolate dùng như service.  
**Lý do:** AGPL khớp với DMOJ/CMS và giữ cải tiến hosted mở; CLA giữ quyền dual-license.  
**Hệ quả:** Thêm `THIRD_PARTY_NOTICES.md`; ghi nguồn từng file copy; không copy spec text không có license.

### D11 — Package authoring và activation trong v1

**Quyết định:** v1 nhập package qua Django admin + management command `import_problem_package`; API upload để sau. Server nhận ZIP, tự derive `manifest.json` nếu tác giả không cung cấp, validate cặp `.in/.ans`, hash từng file, giới hạn số case/kích thước, và chặn path traversal. Activation là hành động rõ ràng của staff; mỗi problem có thể có nhiều version nhưng chỉ một `is_active=True`. Activation **không tự động rejudge**; admin chạy rejudge riêng.

**Lý do:** Cần một đường authoring tối thiểu để self-hoster tạo bài; admin + command đủ cho v1, không cần API upload phức tạp. Manifest do server derive giảm lỗi người dùng, nhưng vẫn cho phép manifest tùy chỉnh cho points/groups/checker.

**Hệ quả:** `ProblemTestData` được thay bằng `ProblemPackage` + `ProblemTestCase.package`; migration map dữ liệu cũ nếu có. Thêm test import package, validation, activation, và fixture seed cho CI.

### D12 — Server là nguồn điểm cuối cùng

**Quyết định:** Worker gửi per-case result; server map case → group từ package của job, recompute `Submission.points` và `subtask_scores` theo group mode. `finish.points` chỉ là cross-check, không được tin tuyệt đối. Worker không cần gửi group scores.

**Lý do:** Tránh worker cũ/độc hại ghi điểm sai; đảm bảo mọi thay đổi scoring đều nằm ở control plane; hỗ trợ rejudge theo package.

**Hệ quả:** Thêm `Submission.subtask_scores` JSON và `SubmissionTestCase.group`; claim response phải kèm group definitions; test IOI group scoring.

### D13 — Manifest và DB: phân quyền rõ

**Quyết định:** Manifest/package là authoritative cho **test cases, checker, group definitions và group points**. DB `Problem.time_limit`, `Problem.memory_limit`, `LanguageLimit`, `ContestProblem.points` là authoritative cho **runtime limits và contest points**; tất cả được gửi trong claim. Đổi limit không cần package mới; đổi case/checker/group points phải tạo package version mới.

**Lý do:** Test data phải immutable để cache/rejudge; limits/contest points là metadata vận hành, thay đổi thường xuyên hơn. Tách hai loại tránh đóng băng nhầm cấu hình.

**Hệ quả:** Claim payload có `limits`, `short_circuit`, `partial_score`, `groups`, `contest_points`; worker dùng đúng các giá trị này; test reproducibility.

### D14 — Pretests ngoài v1

**Quyết định:** v1 luôn chấm full active package. `is_pretest`/`run_pretests_only` được giữ trong schema nhưng không được dùng; pretest/full split là post-v1.

**Lý do:** Pretests thêm phase chấm thứ hai, rejudge và ranking provisional; không cần cho acceptance v1.

**Hệ quả:** Ghi rõ trong docs; test đảm bảo full package được dùng; không leak system tests vì không có khái niệm pretest trong v1.

---

## 5. Kiến trúc

```
┌─────────────────────────────┐
│ Frontend / Swagger / SDK    │
└──────────────┬──────────────┘
               │ HTTPS + JWT
┌──────────────▼──────────────┐
│ Django control plane        │
│  - public API               │
│  - judge API (token riêng)  │
│  - WebSocket consumers      │
│  - Celery tasks             │
└──────┬───────────┬──────────┘
       │           │
       │           └──────────────► Redis (cache, broker, channel layer)
       │
┌──────▼──────────┐       ┌─────────────────────┐
│ PostgreSQL      │       │ S3 / MinIO          │
│ submissions,    │       │ problem packages    │
│ jobs, rankings  │       │ source archives     │
└─────────────────┘       └─────────────────────┘
                                      ▲
                                      │ HTTPS download by hash
┌─────────────────────────────────────┴──────┐
│ Judge worker (Go)                          │
│  - claim job / heartbeat                   │
│  - download package + source               │
│  - go-judge (isolate adapter post-v1)      │
│  - run checker                             │
│  - post case/finish results                │
└────────────────────────────────────────────┘
```

### Thành phần

- **Control plane**: Django, Ninja, service layer, Celery, Channels.
- **Judge gateway**: router `/api/v1/judge/*` trong Django; auth token riêng; không dùng session/JWT user.
- **Worker**: Go binary/container; cấu hình `JUDGE_API_URL`, `JUDGE_TOKEN`, `JUDGE_NAME`, `GO_JUDGE_URL`; poll claim.
- **Execution**: go-judge trong v1; mỗi job chạy trong box riêng; compile/run/checker. isolate chỉ là adapter post-v1.
- **Storage**: Postgres cho metadata; Redis cho cache/broker/channel; S3/MinIO cho package.
- **Observability**: structured logs, metrics (queue depth, claim latency, judge success rate), Sentry.

### Luồng chấm bài

1. Client `POST /api/v1/submissions` với `problem_code`, `language`, `source`, optional `contest_participation`.
2. `SubmissionService` validate source size, language, rate limit; tạo `Submission` + source; tạo `JudgeJob` trong cùng transaction.
3. Publish event `submission.status` sau `on_commit`; broadcast WebSocket.
4. Worker gọi `POST /api/v1/judge/jobs/claim` (long-poll, capabilities). Server claim job bằng `select_for_update(skip_locked=True)`, set lease, trả payload.
5. Worker tải package theo `package_sha256`; verify hash; extract vào temp dir; compile; chạy từng case trong sandbox.
6. Worker gửi batch `POST /api/v1/judge/jobs/{id}/cases`; server upsert `SubmissionTestCase`, update counters, broadcast.
7. Worker gửi `finish`/`fail`; server set final status/result/points; mark job succeeded/failed; publish `submission.finished`.
8. Nếu worker chết: lease hết hạn; server requeue job (tối đa `max_attempts`), rồi đánh dấu `IE` nếu vượt.
9. Contest ranking/recalc chạy sau khi submission final (debounce) hoặc theo tick.

### State machine

**Submission:** `Q` queued → `CP` claimed/compiling → `JG` judging → `CM` completed / `ER` error.  
**JudgeJob:** `queued` → `claimed` → `running` → `succeeded` / `failed` / `expired` / `cancelled`.  
**Case result:** `AC`, `WA`, `TLE`, `MLE`, `RTE`, `CE`, `OLE`, `IR`, `IE`, `PT`.

---

## 6. Data model

### `Judge`

Giữ các field hiện có, thêm:

- `token_hash` (thay vì lưu `auth_key` plaintext; hoặc giữ `auth_key` nhưng hash khi so sánh)
- `protocol_version` (int)
- `capabilities` (JSON: languages, sandbox, max_concurrency)
- `last_seen` (datetime, indexed)
- `status` (online/offline/draining/blocked)
- `current_load` (float)
- `cached_packages` (M2M hoặc JSON danh sách hash gần nhất)

Bỏ dependence vào `problems` M2M cho dispatch; dùng `cached_packages`/hash để quyết định.

### `JudgeJob`

- `id` UUID (hoặc BigAuto + public UUID)
- `submission` FK
- `status` (queued/claimed/running/succeeded/failed/expired/cancelled)
- `priority` int
- `language_id`
- `required_package_sha256`
- `claimed_by` FK Judge nullable
- `lease_expires_at` datetime, indexed
- `attempts` int
- `max_attempts` int default 3
- `last_error` text
- `created_at`, `claimed_at`, `started_at`, `finished_at`
- Index: `(status, priority, created_at)`, `(lease_expires_at)`, `(submission_id)`

### `ProblemPackage`

- `problem` FK
- `version` int
- `sha256` char(64), indexed
- `manifest` JSON
- `archive` FileField
- `size_bytes`
- `created_at`
- `is_active` bool
- Unique `(problem, sha256)`

### `ProblemTestCase`

Thay `problem_data` bằng `package` FK; thêm:

- `input_file`, `output_file` (giữ tên field hiện có)
- `input_sha256`, `output_sha256`
- `points`
- `group` (char)
- `is_pretest` (giữ cho tương lai; v1 bỏ qua)
- `order`
- Unique `(package, order)`

`ProblemTestData` cũ được migrate sang `ProblemPackage`; giữ model trong một release nếu cần rollback, sau đó xoá.

### `Submission`

Giữ các field hiện có; thêm:

- `subtask_scores` JSON (server recompute từ case/group)
- `judge_job` reverse relation
- `version`/`updated_at` cho optimistic concurrency (nếu cần)
- `finalized_at` (hoặc dùng `judged_at`)

### `SubmissionTestCase`

Giữ `case_number`, `status`, `time_used`, `memory_used`, `points`, `total_points`, `feedback`, `output`, `batch_number`; thêm `group` (char) và unique `(submission, case_number)`.

### `Contest`

Thêm/sửa:

- `started_at`, `ended_at` (idempotent lifecycle)
- `rankings_dirty_at` (debounce)
- `ranking_version` (cache invalidation)
- `freeze_time` computed từ `start_time + scoreboard_frozen_after`
- Giữ `rate_all`, `rate_exclude`, `rating_floor`, `rating_ceiling`

### `Rating`

Thêm (chuẩn bị Elo-MMR):

- `mean`, `volatility`, `times_ranked`
- Giữ `rating_before`, `rating_after`, `performance`, `rank`
- Unique `(user, contest)`

### `Language`

Giữ metadata; thêm:

- `sandbox_profile` (key cấu hình trong worker, không chứa command tùy ý từ DB)
- `compile_command`/`run_command` chỉ nếu có validation chặt; tốt nhất để worker config.

---

## 7. Judge API v1

Tất cả dưới `/api/v1/judge/`, auth bằng `Authorization: Bearer <judge-token>` hoặc `X-Judge-Token`; TLS bắt buộc ở production. Token được hash trong DB; có thể rotate.

### `POST /register` (hoặc heartbeat đầu tiên)

Request:

```json
{
  "name": "judge-01",
  "protocol_version": 1,
  "capabilities": {
    "languages": ["python3", "cpp17"],
    "max_concurrency": 4,
    "sandbox": "go-judge"
  }
}
```

Response:

```json
{"judge_id": 1, "heartbeat_interval": 10, "claim_wait_seconds": 30}
```

### `POST /heartbeat`

```json
{
  "load": 0.35,
  "running_jobs": 1,
  "cached_packages": ["sha256:...", "sha256:..."]
}
```

Response:

```json
{"ok": true, "next_heartbeat": 10}
```

### `POST /jobs/claim`

Request:

```json
{
  "wait_seconds": 30,
  "languages": ["python3", "cpp17"],
  "max_jobs": 1
}
```

Response 200:

```json
{
  "job_id": "uuid",
  "submission_id": 123,
  "language": "python3",
  "source": "print(1)",
  "limits": {"time": 2.0, "memory": 262144},
  "short_circuit": false,
  "partial_score": true,
  "contest_points": 100.0,
  "package": {
    "problem_id": 7,
    "sha256": "abc...",
    "url": "/api/v1/judge/packages/7?sha256=abc..."
  },
  "checker": {"type": "testlib", "language": "cpp17", "source": "checkers/float.cpp"},
  "cases": [
    {"id": "01", "input": "data/01.in", "answer": "data/01.ans", "points": 10, "group": "g1"}
  ],
  "groups": [
    {"id": "g1", "points": 30, "mode": "min"},
    {"id": "g2", "points": 70, "mode": "sum"}
  ],
  "lease_seconds": 60
}
```

Response 204 nếu không có job trong `wait_seconds`.

### `POST /jobs/{id}/start`

Worker xác nhận bắt đầu; server set `running`, extend lease.

### `POST /jobs/{id}/cases`

Batch:

```json
{
  "cases": [
    {"case_number": 1, "status": "AC", "time_used": 0.03, "memory_used": 1234, "points": 10, "total_points": 10, "feedback": ""}
  ]
}
```

Server upsert idempotent, update submission counters, publish `submission.case`.

### `POST /jobs/{id}/finish`

```json
{
  "status": "completed",
  "result": "AC",
  "points": 100,
  "time_used": 0.12,
  "memory_used": 2048,
  "case_total": 10,
  "case_passed": 10,
  "error_message": ""
}
```

Server finalize in transaction, mark job succeeded, recompute `Submission.points` và `subtask_scores` từ per-case rows + group definitions, cross-check `finish.points`, publish `submission.finished`, enqueue ranking recalc. `finish.points` không phải nguồn tin cậy cuối cùng.

### `POST /jobs/{id}/fail`

```json
{"status": "error", "result": "CE", "error_message": "..."}
```

### `GET /packages/{problem_id}?sha256=...`

Trả ZIP; kiểm tra token, hash, quyền. Production có thể trả signed S3 URL thay vì proxy.

### Lease/retry

- Claim set `lease_expires_at = now + lease_seconds`.
- Worker gửi heartbeat/lease extension mỗi 10s.
- Server cron/claim-scoped check: job `running/claimed` quá lease → `expired`; nếu attempts < max → requeue, ngược lại mark IE.
- `cases`/`finish` idempotent theo `(job_id, case_number)`; worker retry an toàn.

---

## 8. Test data, checker, và test fixtures

### Package layout v1

```
problem.yaml
manifest.json
data/
  01.in
  01.ans
  02.in
  02.ans
checkers/
  float.cpp          # optional
submissions/         # optional, dùng cho test
```

`manifest.json`:

```json
{
  "schema": 1,
  "problem_code": "aplusb",
  "time_limit": 2.0,
  "memory_limit": 262144,
  "checker": {"type": "exact"},
  "cases": [
    {
      "id": "01",
      "input": "data/01.in",
      "answer": "data/01.ans",
      "input_sha256": "...",
      "answer_sha256": "...",
      "points": 10,
      "group": "g1"
    }
  ],
  "groups": [
    {"id": "g1", "points": 30, "mode": "min"}
  ]
}
```

### Checker

- `exact`: so byte/sau khi normalize line endings; dùng cho v1.
- `testlib`: compile `checkers/*.cpp` bằng worker profile; chạy `checker input output contestant_output`; exit code 0/1/2/3/5; `quitp` trả points.
- `interactive`/`communication`: để sau; cần stream API.

### Test fixtures bắt buộc

`tests/fixtures/packages/`:

| Fixture | Mục đích |
|---|---|
| `aplusb/` | 3 case, exact checker, AC/WA |
| `partial/` | 3 subtask, group min/sum, partial score |
| `float_checker/` | checker Testlib với tolerance |
| `tle/` | case buộc TLE |
| `mle/` | case buộc MLE |
| `ce/` | source compile error |
| `rte/` | runtime error |

`tests/fixtures/sources/`:

- `python/ac.py`, `python/wa.py`, `python/tle.py`, `python/mle.py`, `python/ce.py`, `python/rte.py`
- `cpp/ac.cpp`, `cpp/wa.cpp`
- `checker/float.cpp`

### Test matrix

| Test | Kỳ vọng |
|---|---|
| Submit AC → fake worker | Submission `CM/AC`, case 1..n AC, event đúng |
| Submit WA | `CM/WA`, case WA, points đúng |
| Submit TLE/MLE/RTE/CE | status/result đúng, error message |
| Worker claim 2 lần | Không trả cùng job; lease hoạt động |
| Worker chết, lease hết | Job requeue; attempts tăng; quá max → IE |
| Duplicate case/finish | Idempotent, không nhân đôi points |
| Package hash sai | Worker reject; job fail với IE |
| Contest freeze | Public ranking chỉ thấy submission trước freeze; jury thấy đủ |
| ICPC | penalty đúng, bỏ CE/IE, tiebreak last AC |
| Rating | user mới bắt đầu 1500; rate_exclude/floor/ceiling đúng |
| Event bus | WebSocket nhận đúng event type/group |
| Sandbox | Không network, không đọc file ngoài, time/memory limit |

---

## 9. Contest, ranking, rating

### 9.1 Sửa lỗi bắt buộc

- `_is_accepted` đọc `submission.result`; thêm `Submission.is_accepted` để tránh lặp.
- `_submission_queryset` filter `contest_participation_id=participation.id`, `problem_id=contest_problem.problem_id`, và `created_at <= freeze_time` nếu có.
- `_subtask_scores` không đọc `Submission.result` như dict; dùng `Submission.subtask_scores` do server recompute.
- Freeze: `freeze_time = contest.start_time + contest.scoreboard_frozen_after`; public view filter `created_at <= freeze_time`; staff/jury không filter; sau `end_time` unfreeze.
- Ranking cache key `(contest_id, freeze_time, ranking_version)`; invalidate khi participation/submission final thay đổi.

### 9.2 ICPC

- Chỉ tính submission trước AC đầu tiên.
- Bỏ `CE`/`IE` khỏi penalty.
- Penalty = AC time (phút) + 20 × số lần sai trước AC.
- Score = số bài AC; tiebreak = tổng penalty; tie phụ = AC cuối.
- Nguồn: DMOJ `icpc.py`; DOMjudge scoring.

### 9.3 IOI

- Mỗi problem có subtask/group.
- Best score per subtask across submissions.
- Score types: Sum, GroupMin, GroupMul, GroupThreshold (CMS).
- v1 có thể chỉ Sum/GroupMin; ghi rõ limitation.

### 9.4 Freeze/lifecycle

- `contests.tick` mỗi phút: quét contest đến `start_time`/`end_time`; idempotent bằng `started_at`/`ended_at`.
- `recalculate_rankings(contest_id)` sau khi submission final (debounce 5–10s) và tại freeze/end.
- Rating chỉ chạy sau `end_contest`, trong transaction; lock contest.
- Không dùng `transaction.on_commit` cho publish nếu transaction chưa commit.

### 9.5 Rating

- v1: default 1500; `rating_before` lấy rating hiện tại (đã là 1500); lọc `rate_exclude`, `virtual_start is None`, `rate_all`, floor/ceiling.
- Không ghi volatility giả; lưu `mean`/`volatility`/`times_ranked` để nâng cấp.
- v2: Elo-MMR từ DMOJ; recalc all command.

---

## 10. Auth, permissions, events

### Auth

- API: JWT access (15–30 phút) + refresh (dài hạn, rotate/blacklist) bằng `django-ninja-jwt` hoặc equivalent đã kiểm chứng; tất cả endpoint dùng `request.auth`.
- Admin: Django session; chỉ `/admin/` và endpoint nội bộ.
- Judge: token riêng, hash, rotate; không dùng JWT user; TLS; IP allowlist optional.
- Scopes: `read`, `write`, `judge`, `admin`; kiểm tra ở router, không chỉ UI.
- Rate limit: theo user/token; XFF chỉ tin khi có proxy tin cậy.

### Events

- `publish(group, event_type, payload)`; gọi `transaction.on_commit`.
- `submission_{id}`: `submission.status`, `submission.case`, `submission.finished`.
- `contest_{key}`: `contest.ranking`, `contest.lifecycle`.
- `judge_{name}`: `judge.status`.
- Consumer method names khớp event type (dots → underscores).
- Test bằng `WebsocketCommunicator` + `InMemoryChannelLayer`; không dùng `event.broadcast`.

---

## 11. Testing và acceptance criteria

### Test layers

1. **Unit**: model properties, format algorithms, rating, package manifest validation.
2. **API**: Ninja `TestClient`; auth, permissions, pagination, error codes.
3. **Protocol**: fake judge client; claim/lease/retry/idempotency; no real sandbox.
4. **WebSocket**: `WebsocketCommunicator`; groups/types.
5. **Sandbox integration**: Linux-only; go-judge; AC/WA/TLE/MLE/CE; network denied. isolate adapter có test riêng sau v1.
6. **Contest**: freeze, ICPC, IOI, rating exclusions.
7. **Load smoke**: 100 submissions, 4 workers; queue drains; no double-claim.

### CI

- `ruff check`, `ruff format --check`, `mypy`.
- `python manage.py makemigrations --check --dry-run`.
- `pytest` on Postgres + Redis service; SQLite only for quick local.
- Coverage gate (e.g. 80%) on core apps.
- Optional Linux job for sandbox integration.

### Acceptance criteria v1

- Fresh DB: `migrate` creates all tables; `makemigrations --check` clean.
- Staff imports a package via admin/management command; manifest/hashes validate; one active package; rejudge uses the same package.
- User submits Python A+B via Swagger; worker claims; go-judge runs it; returns AC; per-case rows correct; WebSocket updates.
- Rejudge works; lease expiry requeues; duplicate callbacks idempotent.
- Contest freezes correctly; ICPC ranking correct; rating initial 1500 and exclusions correct.
- v1 chấm full active package; pretests không được dùng.
- All tests pass on Postgres; no real code execution in Django/Celery process.
- Docker Compose up: web, worker, Postgres, Redis, MinIO, go-judge.

---

## 12. Roadmap

### Phase 0 — Baseline (1 tuần)

- Pin Django 5.2 LTS; align metadata.
- Generate initial migrations; CI check.
- Fix scoring field names, freeze, rating default/exclusions.
- Fix event bus contract; add tests.
- Unify auth (JWT) and remove session/JWT split.

### Phase 1 — Judge core API + package authoring (3 tuần)

- `ProblemPackage`, `JudgeJob`, package manifest, hash.
- Admin ZIP upload + `import_problem_package`; derive/validate manifest; activation.
- Judge API: register/heartbeat/claim/cases/finish/fail/package.
- Fake worker tests; lease/retry/idempotency.
- Swagger docs.

### Phase 2 — Real worker + sandbox (3 tuần)

- Go worker; go-judge integration (isolate adapter post-v1).
- Python 3 + C++17 profiles; compile/run/checker.
- Testlib checker; test fixtures.
- Docker Compose for Linux; sandbox tests.

### Phase 3 — Contest/rating (2 tuần)

- ICPC/IOI/freeze; ranking cache; lifecycle tick.
- Rating Elo fix; data migration; recalc command.
- Test matrix.

### Phase 4 — International (2 tuần)

- LocaleMiddleware + gettext; English docs; Vi/En.
- OIDC/email verification/password reset.
- S3/MinIO; API versioning; observability.
- Release docs.

### Phase 5 — LeetCode adapter (sau v1)

- Problem mode `function`.
- Per-language harness; JSON args/expected; harness protocol.
- Separate runner profile; no change to control plane.

---

## 13. Rủi ro và câu hỏi mở

1. **License**: AGPL + CLA (khuyến nghị) hay Apache-2.0? Nếu chọn Apache, không copy được DMOJ/CMS AGPL; chỉ học pattern.
2. **Worker runtime**: Linux-only có chấp nhận không? Windows dev cần WSL/Docker.
3. **Scale mục tiêu**: self-host nhóm nhỏ hay public nhiều contest? Ảnh hưởng số worker, object storage, K8s.
4. **Ngôn ngữ v1**: Python + C++17 đủ chưa? Java/JS/Go/Rust thêm sau?
5. **Interactive/communication**: có cần trong v1 không? Nếu có, protocol phức tạp hơn.
6. **Django 5.2 LTS**: có dependency nào bắt buộc 6.0 không? Nếu có, ghi exception.
7. **CLS/scoreboard**: có cần CCS API adapter ngay không? Để sau.

---

## 14. Phần để builder quyết

- Cấu trúc package Go worker, cách quản lý process/lease.
- go-judge profile cụ thể cho từng language; compile/run flags.
- Helm/K8s manifests; Docker Compose chi tiết.
- Tên field/index cuối cùng; migration strategy.
- UI/UX frontend.
- Các tối ưu ranking cache sau khi có số đo.

---

## 15. Nguồn chính

- Research report: [`docs/research/open-source-online-judges.md`](../../research/open-source-online-judges.md)
- DMOJ: [online-judge](https://github.com/DMOJ/online-judge), [judge-server](https://github.com/DMOJ/judge-server)
- CMS: [cms-dev/cms](https://github.com/cms-dev/cms)
- DOMjudge: [DOMjudge/domjudge](https://github.com/DOMjudge/domjudge)
- Hydro: [hydro-dev/Hydro](https://github.com/hydro-dev/Hydro)
- Judge0: [judge0/judge0](https://github.com/judge0/judge0)
- go-judge: [criyle/go-judge](https://github.com/criyle/go-judge)
- isolate: [ioi/isolate](https://github.com/ioi/isolate)
- Testlib: [MikeMirzayanov/testlib](https://github.com/MikeMirzayanov/testlib)
- Kattis package format: [kattis.com/problem-package-format](https://www.kattis.com/problem-package-format/)
- CCS API: [ccs-specs.icpc.io](https://ccs-specs.icpc.io/)
- Django 5.2 transactions: [docs.djangoproject.com/en/5.2/topics/db/transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions)
- Django select_for_update: [docs.djangoproject.com/en/5.2/ref/models/querysets](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update)
- Django Ninja auth/testing: [django-ninja.dev](https://django-ninja.dev/)
- Channels testing: [channels.readthedocs.io](https://channels.readthedocs.io/en/latest/topics/testing.html)
