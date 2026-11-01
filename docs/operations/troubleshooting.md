[🏠 Project README](../../README.md) · [📚 Documentation](../README.md) · [← Deployment](deployment.md) · [Next: Testing →](../development/testing.md)

# 🧯 Troubleshooting

Start with the health endpoints and logs:

```bash
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready

docker compose ps
docker compose logs --tail 100 web
docker compose logs --tail 100 judge-worker
docker compose logs --tail 100 go-judge
```

> [!TIP]
> Never paste tokens, `.env` contents, or private test data into an issue.
> Redact secrets before sharing logs.

---

## 🔐 Authentication and routing

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| Worker `404 /api/v1/register` | `JUDGELOOM_API_URL` lacks `/judge` | Set `http://web:8000/api/v1/judge` or the HTTPS equivalent |
| Worker `401` | Token does not match the judge record | Create/rotate with `create_judge_token`; update `JUDGELOOM_JUDGE_TOKEN` |
| Worker `403` | Judge blocked | Unblock in the judge admin/API |
| API `401` | Missing/expired JWT | Log in again; send `Authorization: Bearer <token>` |
| Submit endpoint `"Authentication required"` | Session-only request without JWT/session | Use the JWT header or a session client |
| `404` on a public detail page | Private/unknown resource | Check visibility and ownership |

---

## 📦 Package cache

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| `permission denied: ...worker-cache` | Named volume is root-owned | Chown to uid `10001` or recreate the volume; new volumes inherit image ownership |
| `package file hash mismatch` | Corrupt/stale package cache | Remove the cached package directory; the worker re-downloads |
| `package contains no test cases` | Manifest/case paths are wrong | Validate the ZIP; see [Package format](../reference/package-format.md) |
| Worker stays idle | No active package, wrong language, or worker offline | Check `JudgeJob` state, package active flag, and `WORKER_LANGUAGES` |

---

## 🧠 Redis and Celery

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| `NOAUTH Authentication required` | Redis password missing from URL | Set `REDIS_PASSWORD` and password-bearing `REDIS_URL`/broker/channel URLs |
| Celery retries/connection errors | Broker URL points to `localhost` from a container | Use `redis://redis:6379/1` inside Compose |
| Flower cannot connect | Missing broker env/command | Set `CELERY_BROKER_URL` and `--broker` with the password |
| Sessions disappear after restart | Redis persistence/volume not configured | Add AOF/volume or use a managed Redis |

---

## ⚖️ Judge and sandbox

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| `go-judge unhealthy` | Docker daemon/cgroup issue | `docker compose logs go-judge`; verify privileged + `/sys/fs/cgroup` |
| `go-judge 401` on `/run` | Worker token mismatch | Align `GO_JUDGE_TOKEN` and `GO_JUDGE_AUTH_TOKEN` |
| Worker exits at self-test | go-judge URL/token/version invalid | Check `GO_JUDGE_URL`, token, and `/version` |
| C++ compile fails | Image lacks `g++` | Rebuild `docker/Dockerfile.gojudge` |
| TLE/MLE unexpectedly | Limits too tight or checker/interactor overhead | Check limits and [worker runbook](../judge/worker.md) |
| Interactive case hangs | Protocol/pipe mapping or interactor contract | Review [interactive checker notes](../judge/protocol-v1.md) |

---

## 🌐 Web, TLS, and assets

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| `502 Bad Gateway` | Proxy points to wrong web port/host | Proxy to `127.0.0.1:8000`; check `docker compose ps` |
| Redirect loop | Proxy does not set `X-Forwarded-Proto: https` | Configure the proxy to overwrite the header |
| `DisallowedHost` | `DJANGO_ALLOWED_HOSTS` missing the domain | Set the public hostname |
| Static files 404 | nginx path/volume mismatch | Serve the `static_files` volume; run `collectstatic` during build |
| Production won't start: `DJANGO_SECRET_KEY` | Placeholder/short key | Generate a unique 50+ character key |
| `REDIS_PASSWORD is missing` | Production Compose requirement | Set it in `.env`/secret manager |
| `DJANGO_SECRET_KEY is missing` | Production Compose requirement | Set it in `.env`/secret manager |

---

## 🧪 Tests and local development

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| Sandbox tests skip | `GO_JUDGE_URL` unset | Start go-judge and run `bash worker/scripts/test-sandbox.sh` |
| Postgres-only test skipped locally | SQLite test database | Run against PostgreSQL or in CI |
| Migration errors | Database out of date | `python manage.py migrate` |
| `corsheaders` import error | Production requirements not installed | Install `requirements/production.txt` or use the production image |
| Docker build fails at `collectstatic` | Static root not writable | Rebuild the image; it writes to `/var/judgeloom/static` |

---

## 🧭 Useful commands

```bash
# Control plane
docker compose exec web python manage.py check
docker compose exec web python manage.py migrate --noinput
docker compose exec web python manage.py seed_languages

# Worker/judge
docker compose logs -f judge-worker
docker compose exec redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" ping
curl -fsS http://127.0.0.1:5050/version

# Tests
pytest -q
ruff check .
cd worker && go test ./...
bash worker/scripts/test-sandbox.sh
```

---

## 🔗 Related documentation

- [Deployment](deployment.md)
- [Configuration](../getting-started/configuration.md)
- [Worker runbook](../judge/worker.md)
- [Security model](../architecture/security.md)

---

<div align="center">
  <sub>← <a href="deployment.md">Deployment</a> · <a href="../README.md">Documentation hub</a> · <a href="../development/testing.md">Testing</a> →</sub>
</div>
