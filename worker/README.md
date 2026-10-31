# JudgeLoom Worker

Pull-based Go worker for JudgeLoom. It claims jobs from the Django control
plane, downloads the content-addressed test package, executes Python/C++ in
go-judge, applies the exact/Testlib checker, and posts results back.

## Requirements

- Linux (or WSL2) with Docker
- A judge record/token:
  `python manage.py create_judge_token judge-worker-1`
- The token from that command in `JUDGELOOM_JUDGE_TOKEN`

## Run with Compose

```bash
cp .env.example .env
# set JUDGELOOM_JUDGE_TOKEN to the token printed by create_judge_token
docker compose up -d postgres redis web go-judge judge-worker
docker compose logs -f judge-worker
```

`go-judge` runs privileged because it creates Linux namespaces/cgroups. Do not
expose it publicly. Supported v1 languages: `PY3`, `CPP17`.

## Run the unit tests

```bash
cd worker
go test ./...
```

Sandbox integration tests require a running go-judge and are documented in
`docs/judge/worker.md`.
