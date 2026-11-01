[🏠 Project README](../../README.md) · [📚 Documentation](../README.md) · [← Troubleshooting](../operations/troubleshooting.md) · [Next: API reference →](../reference/api.md)

# 🧪 Testing and verification

JudgeLoom has two test surfaces:

- **Django control plane** — pytest + pytest-django.
- **Go worker and sandbox** — Go unit tests plus real go-judge integration.

CI runs both; the real sandbox job requires Docker with Linux containers.

---

## 🐍 Django

```bash
python -m pytest -q
python -m ruff check .
```

The suite covers API auth, package import, scoring, contests, ratings,
submissions, WebSocket behavior, security regressions, secret validation, and
worker protocol paths. On a local SQLite run, the Postgres-only claim
concurrency test is skipped; CI runs it against PostgreSQL.

Useful subsets:

```bash
pytest tests/test_judge_gateway.py -v
pytest tests/test_judge_e2e.py -v
pytest tests/test_security_regressions.py -v
pytest tests/test_password_validation.py -v
```

---

## 🐹 Go worker

```bash
cd worker
gofmt -l .
go vet ./...
go test ./...
```

The unit tests cover API client paths, package extraction, runner behavior,
checker/validator logic, authoring, and worker execution mapping.

---

## 🧱 Real go-judge integration

The integration suite runs sandboxed Python/C++, Testlib checker/validator,
interactive checker, and the package generator against a real go-judge:

```bash
# Starts/reuses the Compose go-judge and verifies token auth
bash worker/scripts/test-sandbox.sh
```

Requirements:

- Docker daemon with Linux containers
- a running/token-protected go-judge
- `GO_JUDGE_URL` (the script sets it)
- `GO_JUDGE_TOKEN` or `GO_JUDGE_AUTH_TOKEN` matching the sandbox

The script checks that anonymous `/run` returns `401` before running the tests.

---

## 🐳 Build and Compose checks

```bash
docker compose config >/dev/null
docker compose -f docker-compose.yml -f docker-compose.prod.yml config >/dev/null
docker build -f docker/Dockerfile --target runtime -t judgeloom-core:test .
```

The production build runs `collectstatic` with a fresh build-only secret. It
also verifies that production settings can import with a writable static root.

---

## 🧭 Test layers

| Layer | Command | What it proves |
| :--- | :--- | :--- |
| Lint | `ruff check .` | Style/import/static rules |
| Unit | `pytest -q`, `go test ./...` | Logic and contracts |
| API/auth | targeted pytest files | JWT/session, ownership, visibility |
| Sandbox | `bash worker/scripts/test-sandbox.sh` | Real isolation and verdicts |
| Deployment | Compose render + image build | Configuration validity |
| Security | Semgrep / audit run | Pattern and boundary review |

---

## 📝 Documentation checks

Documentation is part of the product. When changing routes, environment
variables, or deployment commands, update the relevant Markdown files and
verify local links. The docs hub is [docs/README.md](../README.md).

---

## 🤝 Contributing

Read the [Contributing guide](../../CONTRIBUTING.md) for branch, commit, and PR
conventions. In short: keep changes tested, typed, linted, and documented.

---

## 🔗 Related documentation

- [Quickstart](../getting-started/quickstart.md)
- [Deployment](../operations/deployment.md)
- [Troubleshooting](../operations/troubleshooting.md)
- [Worker runbook](../judge/worker.md)

---

<div align="center">
  <sub>← <a href="../operations/troubleshooting.md">Troubleshooting</a> · <a href="../README.md">Documentation hub</a> · <a href="../reference/api.md">API reference</a> →</sub>
</div>
