# JudgeLoom Worker + Sandbox (Plan B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real Go judge worker that polls the Plan A control plane, downloads content-addressed packages, compiles/runs Python and C++ in go-judge, applies exact/Testlib checkers, and reports per-case/final results.

**Architecture:** The worker is a stateless Go process. It claims one leased `JudgeJob`, verifies the package SHA-256, extracts it into a private temp directory, calls go-judge over HTTP for compile/run, scores each case locally using the package manifest, posts batched case results, and finalizes through the existing `/api/v1/judge` API. Django remains the source of truth for points and verdicts.

**Tech Stack:** Go 1.27+, go-judge v1.13.x (MIT), Testlib 0.9.41 (MIT), Docker Compose, Python 3 and C++17 runtimes. Control plane stays Django 5.2 LTS.

**Spec:** `docs/superpowers/specs/2026-10-30-judgeloom-core-design.md`

## Global Constraints

- Worker runs on Linux only; go-judge is the only execution backend in Plan B. `isolate` is a later adapter.
- Never interpolate user source into a shell command. go-judge receives `args` arrays and file contents only.
- Verify the package SHA-256 before extraction; reject path traversal, absolute paths, oversized archives, and oversized uncompressed contents.
- The server remains authoritative for final points/verdicts; worker-computed points are only for per-case reporting.
- Use the existing judge bearer token; do not use user JWT/session.
- Send `package_sha256` on `cases`, `finish`, and `fail`; the server rejects a mismatch with 409.
- Heartbeat every 10 seconds; the server extends leases for the worker's active jobs.
- Worker code must be standard-library-only unless a dependency is justified in the task.
- Run tests on Linux (Docker/WSL) for sandbox integration; unit tests must also run on Windows.
- Do not copy go-judge/Testlib code; integrate them as services/vendored header with notices.

## Review Focus

- Worker dies after claim → heartbeat stops, lease expires, server requeues; the worker never reports a stale final result.
- Package hash mismatch → worker refuses to execute or reports `IE`, never grades stale data.
- Malicious source tries network/filesystem escape → go-judge denies it; worker does not shell-escape source.
- Output exceeds limit → go-judge returns OutputLimitExceeded, worker reports OLE not a crash.
- Checker returns `_points` (`quitp`) or non-zero codes → worker maps to PT/WA/PE correctly.
- Compile fails or runtime signal → worker reports CE/RTE and does not run cases.
- Two workers process one job → server lease prevents double execution.

---

### Task 1: Go module, config, and judge HTTP client

**Files:**
- Create: `worker/go.mod`
- Create: `worker/cmd/judgeloom-worker/main.go`
- Create: `worker/internal/config/config.go`
- Create: `worker/internal/api/types.go`
- Create: `worker/internal/api/client.go`
- Create: `worker/internal/api/client_test.go`

**Interfaces:**
- Consumes: Plan A `/api/v1/judge` routes and judge token.
- Produces:

```go
type Config struct {
    APIURL       string
    JudgeToken   string
    JudgeName    string
    PollInterval time.Duration
    Heartbeat    time.Duration
    CacheDir     string
}

type Client interface {
    Register(ctx context.Context, req RegisterRequest) (RegisterResponse, error)
    Heartbeat(ctx context.Context, req HeartbeatRequest) error
    Claim(ctx context.Context, req ClaimRequest) (*Job, error)
    Start(ctx context.Context, jobID int64) error
    Cases(ctx context.Context, jobID int64, req CasesRequest) error
    Finish(ctx context.Context, jobID int64, req FinishRequest) error
    Fail(ctx context.Context, jobID int64, req FailRequest) error
    DownloadPackage(ctx context.Context, problemID int64, sha256 string) ([]byte, error)
}

type Job struct {
    JobID        int64
    SubmissionID int64
    Language     string
    Source       string
    Limits       struct{ Time float64; Memory int64 }
    ShortCircuit bool
    PartialScore bool
    ContestPoints *float64
    Package      struct{ ProblemID int64; SHA256, URL string }
    Checker      Checker
    Cases        []Case
    Groups       []Group
    LeaseSeconds int
}

type Checker struct {
    Type     string
    Language string
    Source   string
}

type Case struct {
    ID, Input, Answer string
    Points            float64
    Group             string
}

type Group struct {
    ID     string
    Points float64
    Mode   string
}

type CaseResult struct {
    CaseNumber  int
    Status      string
    TimeUsed    float64
    MemoryUsed  int64
    Points      float64
    TotalPoints float64
    Feedback    string
    Output      string
}
```

The exact JSON tags must match `docs/judge/protocol-v1.md`; `Limits.Time` is seconds, `Memory` is KB in the API and must be converted to bytes for go-judge.

- [ ] **Step 1: Write failing client tests with `httptest`**

Test `Claim` sends `POST /jobs/claim` with `Authorization: Bearer secret`, decodes 200, and returns `(nil, nil)` on 204. Test `Cases`, `Finish`, `Fail`, and `DownloadPackage` use the correct methods/paths and reject non-2xx with the server's `error`/`code`.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd worker && go test ./internal/api -run TestClient -v
```

Expected: fail because the package does not exist.

- [ ] **Step 3: Implement config and client**

Use `net/http`, `encoding/json`, `context`, and `time`. Base URL is `JUDGELOOM_API_URL` (default `http://localhost:8000/api/v1`). All requests set `Authorization: Bearer <token>` and `Content-Type: application/json`. Decode 204 claims as `nil, nil`. `DownloadPackage` verifies the returned bytes' SHA-256 and returns `ErrHashMismatch` on mismatch.

- [ ] **Step 4: Add a minimal `main.go`**

Parse config from environment, construct the client, and exit non-zero on missing token/name. No worker loop yet.

- [ ] **Step 5: Run tests and commit**

```bash
cd worker && gofmt -w . && go test ./...
git add worker
git commit -m "feat(worker): add config and judge API client"
```

---

### Task 2: Worker loop, registration, heartbeat, and job lifecycle

**Files:**
- Create: `worker/internal/worker/worker.go`
- Create: `worker/internal/worker/worker_test.go`
- Modify: `worker/cmd/judgeloom-worker/main.go`

**Interfaces:**
- Consumes: `api.Client` from Task 1.
- Produces:

```go
type Executor interface {
    Execute(ctx context.Context, job *api.Job) ([]api.CaseResult, error)
}

type Worker struct {
    Client    api.Client
    Executor  Executor
    Languages []string
    Poll      time.Duration
}

func (w *Worker) Run(ctx context.Context) error
```

- [ ] **Step 1: Write failing loop tests with a fake client**

Test that `Run` calls `Register`, starts a heartbeat goroutine, claims a job, calls `Start`, calls `Executor.Execute`, posts `Cases`, calls `Finish`, and sleeps/polls when claim returns nil. Test cancellation exits cleanly.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd worker && go test ./internal/worker -run TestWorker -v
```

- [ ] **Step 3: Implement the loop**

Register with `protocol_version: 1` and capabilities (languages, `sandbox: "go-judge"`). Heartbeat ticker every configured interval; on claim, call `Start`, execute, post cases in one batch, then `Finish`. If execute returns a compile/internal error, call `Fail` with `CE`/`IE`. Never call `Finish` and `Fail` for the same attempt.

- [ ] **Step 4: Wire `main.go` and graceful shutdown**

Use `signal.NotifyContext` for `SIGINT`/`SIGTERM`; pass the context to `Run`. Log job id, submission id, language, and verdict; never log source code.

- [ ] **Step 5: Run tests and commit**

```bash
cd worker && go test ./... && go vet ./...
git add worker
git commit -m "feat(worker): add poll loop and heartbeat"
```

---

### Task 3: Package download, extraction, and cache

**Files:**
- Create: `worker/internal/package/store.go`
- Create: `worker/internal/package/store_test.go`

**Interfaces:**
- Consumes: `api.Client.DownloadPackage` and package ZIP/manifest contract from Protocol v1.
- Produces:

```go
type Store struct { Root string; Client api.Client }
func (s *Store) Ensure(ctx context.Context, problemID int64, sha256 string) (string, error)
// Ensure verifies the archive hash, safely extracts to Root/<sha256>/,
// and returns the extracted package directory.
```

- [ ] **Step 1: Write failing tests**

Test a valid package extracts to the hash directory; a wrong archive hash returns `ErrHashMismatch`; `../` and absolute ZIP entries return an error; a second `Ensure` with the same hash does not download again; concurrent `Ensure` calls do not corrupt the directory.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd worker && go test ./internal/package -run TestStore -v
```

- [ ] **Step 3: Implement safe extraction**

Use `archive/zip`, `crypto/sha256`, `os.MkdirTemp`, `os.Rename` for atomic publish. Reject entries with `..`, absolute paths, or drive prefixes. Cap archive bytes (`64 MiB`), uncompressed bytes (`256 MiB`), and file count (`200`). Verify per-case `input_sha256`/`answer_sha256` before execution. Clean partial temp dirs on error.

- [ ] **Step 4: Implement cache cleanup**

Provide `Cleanup(maxAge time.Duration)` that removes cache directories older than maxAge; call it from `main.go` at startup.

- [ ] **Step 5: Run tests and commit**

```bash
cd worker && go test ./internal/package -v
git add worker
git commit -m "feat(worker): cache and safely extract problem packages"
```

---

### Task 4: go-judge executor

**Files:**
- Create: `worker/internal/executor/gojudge.go`
- Create: `worker/internal/executor/gojudge_test.go`

**Interfaces:**
- Consumes: go-judge REST `POST /run` from `pb/request.proto` and `pb/response.proto`.
- Produces:

```go
type GoJudge struct {
    BaseURL string
    Client  *http.Client
}

type RunSpec struct {
    Args        []string
    Env         []string
    StdIn       []byte
    CopyIn      map[string][]byte
    CPUTime     time.Duration
    ClockTime   time.Duration
    MemoryBytes int64
    ProcLimit   int
}

type RunResult struct {
    Status     string
    ExitStatus int
    Time       time.Duration
    Memory     int64
    Stdout     []byte
    Stderr     []byte
    FileIDs    map[string]string
    Error      string
}

func (g *GoJudge) Run(ctx context.Context, spec RunSpec) (RunResult, error)
```

- [ ] **Step 1: Write failing request-shape tests with `httptest`**

Assert the request JSON includes `requestID`, `cmd[0].args`, `cmd[0].env`, `cmd[0].cpuTimeLimit` in nanoseconds, `cmd[0].clockTimeLimit`, `cmd[0].memoryLimit` in bytes, `cmd[0].procLimit`, `cmd[0].copyIn` with base64 memory files, and `cmd[0].files` with stdin memory plus `pipe` collectors named `stdout`/`stderr`. Assert response `status`, `exitStatus`, `time`, `memory`, and collected `files` decode into `RunResult`.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd worker && go test ./internal/executor -run TestGoJudge -v
```

- [ ] **Step 3: Implement the REST adapter**

Map go-judge statuses: `Accepted` → OK; `TimeLimitExceeded` → TLE; `MemoryLimitExceeded` → MLE; `OutputLimitExceeded` → OLE; `NonZeroExitStatus` → RTE; `Signalled` → RTE; `DangerousSyscall`/`InternalError` → IE. Decode base64 `files` into stdout/stderr. Map HTTP/network failures to `IE` with a bounded retry (2 attempts, 1s backoff), not an infinite loop.

- [ ] **Step 4: Run tests and commit**

```bash
cd worker && go test ./internal/executor -v
git add worker
git commit -m "feat(worker): execute jobs through go-judge"
```

---

### Task 5: Language profiles and compile/run flow

**Files:**
- Create: `worker/internal/language/profiles.go`
- Create: `worker/internal/runner/runner.go`
- Create: `worker/internal/runner/runner_test.go`

**Interfaces:**
- Consumes: `executor.GoJudge`.
- Produces:

```go
type Profile struct {
    Key        string
    SourceName string
    Compile    *executor.RunSpec
    Run        executor.RunSpec
}

type Runner struct {
    Judge *executor.GoJudge
}

func Get(key string) (Profile, bool)
func (r *Runner) CompileAndRun(ctx context.Context, language, source string, input []byte, timeLimit time.Duration, memoryLimit int64) (executor.RunResult, error)
```

- [ ] **Step 1: Write failing profile tests**

Assert `PY3` writes source as `main.py` and runs `python3 main.py` with stdin; `CPP17` writes `main.cpp`, compiles with `g++ -O2 -std=c++17 -o main main.cpp`, caches the `main` file ID, then runs the cached binary with stdin. Unknown language returns a typed `ErrUnsupportedLanguage`.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd worker && go test ./internal/runner -run TestRunner -v
```

- [ ] **Step 3: Implement compile/run**

Python: no compile. C++: compile with `copyOutCached: [{"name":"main"}]`, read the cached file ID, then run `["/w/main"]` with `copyIn` using the cached file. Set `cpuTimeLimit` from the package limit, `clockTimeLimit` = 2× CPU, `memoryLimit` from bytes, `procLimit=64`. Treat compile non-zero as CE and never run cases. Use a fresh temp working directory per job.

- [ ] **Step 4: Run tests and commit**

```bash
cd worker && go test ./internal/runner -v
git add worker
git commit -m "feat(worker): add Python and C++ runtime profiles"
```

---

### Task 6: Exact and Testlib checkers

**Files:**
- Create: `worker/internal/checker/checker.go`
- Create: `worker/internal/checker/checker_test.go`
- Add: `worker/third_party/testlib/testlib.h` with MIT notice

**Interfaces:**
- Consumes: package manifest `checker` field and Testlib exit-code contract.
- Produces:

```go
type Result struct {
    Status  string  // AC|WA|PE|PT|IE
    Points  float64
    Message string
}

type Checker interface {
    Check(ctx context.Context, spec api.Checker, input, answer, output []byte, timeLimit time.Duration, memoryLimit int64) (Result, error)
}

func Exact(input, answer, output []byte) Result
func Testlib(ctx context.Context, runner *runner.Runner, checkerSource []byte, input, answer, output []byte, limits) (Result, error)
```

- [ ] **Step 1: Write failing checker tests**

Exact: identical normalized output → AC; different output → WA. Testlib: exit `0` → AC; `1` → WA; `2` → PE; `3` → IE; `5` → PT with points parsed from the `points` line in stderr; missing checker → IE.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd worker && go test ./internal/checker -run TestChecker -v
```

- [ ] **Step 3: Implement exact and Testlib checkers**

Exact comparison normalizes CRLF and trailing whitespace on each line. Testlib compiles the vendored `testlib.h` checker with `g++ -O2 -std=c++17`, runs it with input/answer/contestant output as three files, maps exit codes, and parses `points` from stderr. Do not execute checker code in the worker process; it runs in go-judge.

- [ ] **Step 4: Run tests and commit**

```bash
cd worker && go test ./internal/checker -v
git add worker
git commit -m "feat(worker): add exact and Testlib checkers"
```

---

### Task 7: Case loop, error mapping, and result reporting

**Files:**
- Create: `worker/internal/worker/execute.go`
- Create: `worker/internal/worker/execute_test.go`
- Modify: `worker/internal/worker/worker.go`

**Interfaces:**
- Consumes: package manifest, runner, checker, API client.
- Produces:

```go
type JobExecutor struct {
    Runner  *runner.Runner
    Checker checker.Checker
}

func (e *JobExecutor) Execute(ctx context.Context, job *api.Job) ([]api.CaseResult, error)
```

- [ ] **Step 1: Write failing execution tests**

Test a two-case package: AC + WA produces two `CaseResult`s with status, time, memory, points, total points, and feedback; compile failure returns a typed CE error; TLE/MLE/RTE/OLE map to the matching SubmissionResult; a checker IE marks the case `IE`; no source code appears in logs.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd worker && go test ./internal/worker -run TestExecute -v
```

- [ ] **Step 3: Implement execution and mapping**

For each manifest case: run the program, apply the checker, build `CaseResult` with `case_number`, status, time, memory, points, total_points, feedback, output. Stop early only if the package/job says `short_circuit` and a case fails; otherwise run all cases. Map runner errors to CE/IE; map go-judge statuses to the control-plane result codes. Do not compute final aggregate points; the server does.

- [ ] **Step 4: Wire reporting**

Post all case results in one `/cases` request with `package_sha256`; then `/finish` with the same hash. On compile/runner infrastructure failure, call `/fail` with `CE` or `IE`. Test idempotent retry does not duplicate case reports.

- [ ] **Step 5: Run tests and commit**

```bash
cd worker && go test ./internal/worker -v
git add worker
git commit -m "feat(worker): execute packages and report case results"
```

---

### Task 8: Docker Compose, worker image, and go-judge service

**Files:**
- Create: `docker/Dockerfile.worker`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Create: `worker/README.md`

**Interfaces:**
- Consumes: worker binary and go-judge image.
- Produces: `judge-worker` + `go-judge` services on the Compose network.

- [ ] **Step 1: Add the worker Dockerfile**

Multi-stage: `golang:1.27` builds the worker; runtime `debian:bookworm-slim` contains the worker, `python3`, `g++`, and CA certificates. Run as a non-root user. No shell wrapper for source.

- [ ] **Step 2: Add Compose services**

Add `go-judge` (`criyle/go-judge:v1.13.3` or the pinned release) with Linux privileges needed for cgroups, `/sys/fs/cgroup` mount, and a healthcheck on `/version`. Add `judge-worker` with `JUDGELOOM_API_URL=http://web:8000/api/v1`, `JUDGELOOM_JUDGE_TOKEN`, `GO_JUDGE_URL=http://go-judge:5050`, and a package cache volume. Do not expose go-judge publicly.

- [ ] **Step 3: Update `.env.example` and docs**

Document `JUDGELOOM_JUDGE_TOKEN`, `GO_JUDGE_URL`, `WORKER_LANGUAGES=PY3,CPP17`, `WORKER_CACHE_DIR`, and the fact that go-judge requires Linux containers.

- [ ] **Step 4: Verify configuration**

```bash
docker compose config
docker compose up -d postgres redis web go-judge judge-worker
docker compose ps
```

Expected: all services healthy; worker logs registration and heartbeat. If Docker is unavailable on Windows, document WSL2/Linux as the supported path.

- [ ] **Step 5: Commit**

```bash
git add docker/Dockerfile.worker docker-compose.yml .env.example worker/README.md
git commit -m "feat(worker): add Docker Compose worker and go-judge services"
```

---

### Task 9: Real go-judge integration tests

**Files:**
- Create: `worker/integration/sandbox_test.go`
- Create: `worker/integration/testdata/aplusb/` (manifest, 01.in, 01.ans)
- Create: `worker/integration/testdata/sources/` (Python/C++ AC, WA, TLE, MLE, CE, RTE)
- Create: `worker/scripts/test-sandbox.sh`

**Interfaces:**
- Consumes: running go-judge and the worker runner/checker packages.
- Produces: Linux-only integration evidence.

- [ ] **Step 1: Write integration tests**

Skip unless `GO_JUDGE_URL` is set. For Python and C++, assert AC, WA, TLE, MLE, CE, RTE. Assert the TLE case reports `TLE`, the compile failure reports `CE` without running cases, and a program attempting network/file escape is denied (or reports RTE/IE, never AC).

- [ ] **Step 2: Add the runner script**

```bash
#!/usr/bin/env bash
set -euo pipefail
docker compose up -d go-judge
GO_JUDGE_URL=http://localhost:5050 go test ./worker/integration -v
```

- [ ] **Step 3: Run on Linux/WSL**

```bash
bash worker/scripts/test-sandbox.sh
```

Expected: all sandbox tests pass; capture the actual go-judge version in the test log.

- [ ] **Step 4: Commit**

```bash
git add worker/integration worker/scripts
git commit -m "test(worker): add real go-judge sandbox coverage"
```

---

### Task 10: Worker runbook and protocol updates

**Files:**
- Create: `docs/judge/worker.md`
- Modify: `README.md`
- Modify: `docs/judge/protocol-v1.md`

**Interfaces:**
- Consumes: completed worker.
- Produces: operator/contributor documentation.

- [ ] **Step 1: Write the runbook**

Cover: judge token creation/rotation, `import_problem_package`, starting Compose, supported languages, go-judge privileges, cache location, logs, metrics, troubleshooting (401/403/404/409, package hash mismatch, go-judge unavailable), and the fact that Windows requires WSL2/Linux.

- [ ] **Step 2: Update README and protocol**

Add a “Run a judge worker” quickstart and the worker environment variables. Update protocol v1 with the worker's actual go-judge status mapping and package hash echo.

- [ ] **Step 3: Run docs checks**

```bash
grep -R "TODO" docs/judge worker || true
```

Expected: no unresolved TODO in the shipped docs.

- [ ] **Step 4: Commit**

```bash
git add docs/judge/worker.md README.md docs/judge/protocol-v1.md
git commit -m "docs: add judge worker runbook"
```

---

## Follow-up

- **Plan B2 — User auth:** replace the custom user JWT with `django-ninja-jwt==5.4.5`, unify API auth, add OAuth/email verification. This is independent of the worker.
- **Plan C — Contest/rating:** fix scoring field names, freeze, ICPC/IOI, lifecycle, Elo-MMR.
- **Plan D — International:** i18n, OIDC, S3/MinIO, API versioning, observability, Helm/K8s.
