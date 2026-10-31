# JudgeLoom Worker Runbook

The worker is a Linux Go process that pulls leased jobs from the Django control
plane and executes Python/C++ through go-judge. It never runs user code in the
Django or Celery process.

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
| `JUDGELOOM_API_URL` | `http://localhost:8000/api/v1` | Control-plane base URL |
| `JUDGELOOM_JUDGE_TOKEN` | required | Bearer token from `create_judge_token` |
| `JUDGELOOM_JUDGE_NAME` | required | Must match the judge record name |
| `GO_JUDGE_URL` | `http://localhost:5050` | go-judge REST endpoint |
| `WORKER_LANGUAGES` | `PY3,CPP17` | Claimed language keys |
| `WORKER_CACHE_DIR` | `./worker-cache` | Package cache directory |
| `WORKER_POLL_INTERVAL` | `2s` | Empty-claim poll delay |
| `WORKER_HEARTBEAT` | `10s` | Heartbeat/lease extension interval |

The worker sends `package_sha256` on cases/finish/fail; the server rejects a
stale package with `409`.

## Compose

```bash
cp .env.example .env
# set JUDGELOOM_JUDGE_TOKEN and JUDGELOOM_JUDGE_NAME
docker compose up -d postgres redis web go-judge judge-worker
docker compose logs -f judge-worker
```

`go-judge` runs privileged because it creates Linux namespaces/cgroups. Bind it
to localhost only; never expose it publicly. The worker image is minimal; the
execution image contains Python 3 and g++.

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
