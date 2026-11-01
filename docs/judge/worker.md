# JudgeLoom Worker Runbook

The worker is a Linux Go process that pulls leased jobs from the Django control
plane and executes Python/C++ through go-judge. It never runs user code in the
Django or Celery process. At startup it calls go-judge `/version` and verifies
`GO_JUDGE_TOKEN` against a protected endpoint; an unreachable sandbox, malformed
version response, or rejected token fails the worker before registration, and
the reported `go_judge_version` is stored in the judge capabilities.

## Prerequisites

- Docker Desktop with Linux containers, or a Linux/WSL2 host
- A judge record and token:

```bash
python manage.py create_judge_token judge-worker-1
# copy the printed token to JUDGELOOM_JUDGE_TOKEN
```

- A problem package imported into JudgeLoom:

```bash
python manage.py import_problem_package aplusb path/to/aplusb.zip
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `JUDGELOOM_API_URL` | `http://localhost:8000/api/v1` | Control-plane base URL; production must be HTTPS |
| `WORKER_ALLOW_INSECURE_HTTP` | `false` | Permit a plaintext control-plane URL for local development only |
| `JUDGELOOM_JUDGE_TOKEN` | required | Bearer token from `create_judge_token` |
| `JUDGELOOM_JUDGE_NAME` | required | Must match the judge record name |
| `GO_JUDGE_URL` | `http://localhost:5050` | go-judge REST endpoint |
| `GO_JUDGE_TOKEN` | empty | Bearer token for go-judge; must match `GO_JUDGE_AUTH_TOKEN` |
| `WORKER_LANGUAGES` | `PY3,CPP17` | Claimed language keys |
| `WORKER_CACHE_DIR` | `./worker-cache` | Package cache directory |
| `WORKER_POLL_INTERVAL` | `2s` | Empty-claim poll delay |
| `WORKER_HEARTBEAT` | `10s` | Heartbeat/lease extension interval |

The worker sends `package_sha256` on cases/finish/fail; the server rejects a
stale package with `409`.

## Compose

```bash
cp .env.example .env
# set JUDGELOOM_JUDGE_TOKEN, JUDGELOOM_JUDGE_NAME and GO_JUDGE_AUTH_TOKEN
docker compose up -d postgres redis web go-judge judge-worker
docker compose logs -f judge-worker
```

`go-judge` runs privileged because it creates Linux namespaces/cgroups. It
listens on a dedicated `judge_net` network reachable only by the judge worker
(the production overlay marks it `internal`, so the sandbox has no egress),
requires the `GO_JUDGE_AUTH_TOKEN` bearer token on execution endpoints, and
starts with `-no-fallback` so a cgroup failure stops execution instead of
silently running without isolation. Its root filesystem is read-only, with
writable `/tmp` (tmpfs), `/dev/shm`, and `/sys/fs/cgroup` only. The development
Compose file publishes `127.0.0.1:5050` for debugging; the production overlay
removes that port entirely. Never expose go-judge publicly. The worker image is
minimal; the execution image contains Python 3 and g++.

## Supported languages (v1)

- `PY3` — `main.py`, run with `python3 main.py`
- `CPP17` — `main.cpp`, compile with `g++ -O2 -std=c++17 -o main main.cpp`,
  run the cached binary as `/w/main`

Checkers: exact comparison and Testlib (exit codes `0/1/2/3/5`; `quitp`
points parsed from stderr).

## Troubleshooting

| Symptom | Check |
|---|---|
| Worker exits: token/name required | Set both `JUDGELOOM_JUDGE_TOKEN` and `JUDGELOOM_JUDGE_NAME` |
| 401 on register | Token does not match the judge's `token_hash`; rotate with `create_judge_token --rotate` |
| 403 | Judge is blocked |
| 404 on package | Package hash is unknown for the problem |
| 409 on cases/finish | Lease expired, stale package hash, or another judge owns the job |
| Worker stays idle | No queued job with a claimed language; check package active version |
| `go-judge` unhealthy | Docker daemon/cgroups; inspect `docker compose logs go-judge` |
| Worker exits: go-judge self-test failed | Check `GO_JUDGE_URL`, go-judge health, and the `/version` response |
| `go-judge 401` on `/run` | `GO_JUDGE_TOKEN` does not match `GO_JUDGE_AUTH_TOKEN`; `/version` stays public for health checks |
| C++ compile fails in sandbox | The go-judge image must include `g++`; rebuild `docker/Dockerfile.gojudge` |

## Tests

```bash
cd worker
go test ./...              # unit tests, Windows or Linux
bash worker/scripts/test-sandbox.sh  # real go-judge integration, Linux/WSL/Docker
```

The real sandbox test covers Python/C++ AC, WA, TLE, MLE, RTE and CE. It skips
when `GO_JUDGE_URL` is unset.

## Deployment notes

- Keep the package cache on a persistent volume.
- Run one worker process per container; scale with Compose/Kubernetes replicas.
- Use TLS between the worker and the control plane in production.
- Do not run go-judge as a public service; it is trusted infrastructure.
- Treat go-judge as host-level trust: run it on dedicated judge hosts (or a
  dedicated VM), not alongside the control plane. A container escape from the
  sandbox is a host compromise.
- Rotate `GO_JUDGE_AUTH_TOKEN` together with the worker deployment; the token
  gates every `/run` call, including interactive replays.
- Keep `/sys/fs/cgroup` writable for go-judge and leave `-no-fallback` enabled.
  Removing either silently weakens sandbox isolation.
- Keep the read-only rootfs and tmpfs `/tmp`; the production overlay also caps
  go-judge at 4 CPUs, 4 GiB, and 4096 pids. Raise them only for measured load.
