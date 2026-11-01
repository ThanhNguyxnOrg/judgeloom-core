[🏠 Project README](../../README.md) · [📚 Documentation](../README.md) · [← Quickstart](quickstart.md) · [Next: First submission →](first-submission.md)

# ⚙️ Configuration

JudgeLoom reads configuration from environment variables via
`django-environ`. `.env` is gitignored; `.env.example` is the source of truth
for supported variables.

> [!WARNING]
> Never commit `.env`. Production rejects known placeholder signing keys and
> requires explicit service secrets.

---

## 🧩 Configuration layers

| Layer | File | Purpose |
| :--- | :--- | :--- |
| Base | `config/settings/base.py` | Shared settings and environment schema |
| Development | `config/settings/development.py` | `DEBUG=True`, SQLite fallback, local toolbar |
| Production | `config/settings/production.py` | HTTPS/HSTS, secure cookies, secret validation |
| Testing | `config/settings/testing.py` | In-memory DB, eager Celery, fast hashing |
| Compose | `docker-compose.yml` + `docker-compose.prod.yml` | Service wiring and secrets |

---

## 🔑 Core Django variables

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` | Use `config.settings.production` in production |
| `DJANGO_SECRET_KEY` | required | JWT HS256 signing key; production requires 50+ unique chars |
| `DJANGO_DEBUG` | `False` | Production settings force `False` regardless |
| `DJANGO_ALLOWED_HOSTS` | empty | Comma-separated hostnames, e.g. `judgeloom.example.com` |
| `TRUST_X_FORWARDED_FOR` | `False` | Only enable behind a trusted proxy |
| `TRUSTED_PROXY_IPS` | empty | IP allowlist used when XFF is trusted |
| `CORS_ALLOWED_ORIGINS` | empty | Comma-separated browser origins |
| `SENTRY_DSN` | empty | Optional; PII sending is disabled |

Generate the signing key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

The production guard rejects known placeholders, short keys, and
`django-insecure-` prefixes. See
[`config/settings/secret.py`](../../config/settings/secret.py).

---

## 🗄️ Database

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `DATABASE_URL` | empty | PostgreSQL URL; empty uses SQLite in development |
| `POSTGRES_DB` | `judgeloom` | Compose database name |
| `POSTGRES_USER` | `judgeloom` | Compose database user |
| `POSTGRES_PASSWORD` | required in prod | Required by the production overlay |

```dotenv
# Local PostgreSQL
DATABASE_URL=postgres://judgeloom:password@localhost:5432/judgeloom

# Local SQLite fallback (development only)
DATABASE_URL=
```

> [!TIP]
> In Docker Compose the web service receives
> `postgres://judgeloom:...@postgres:5432/judgeloom`, so development uses
> PostgreSQL. A bare local run with an empty `DATABASE_URL` uses SQLite.

---

## 🧠 Redis, Celery, and Channels

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `REDIS_PASSWORD` | dev default in Compose | Required in production |
| `REDIS_URL` | `redis://localhost:6379/0` | Cache/session Redis URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery broker |
| `CHANNEL_LAYERS_URL` | `redis://localhost:6379/2` | Django Channels layer |

Use URL-safe characters in the password because it is embedded in URLs:

```dotenv
REDIS_PASSWORD=change-me-to-a-random-url-safe-password
REDIS_URL=redis://:change-me-to-a-random-url-safe-password@localhost:6379/0
CELERY_BROKER_URL=redis://:change-me-to-a-random-url-safe-password@localhost:6379/1
CHANNEL_LAYERS_URL=redis://:change-me-to-a-random-url-safe-password@localhost:6379/2
```

The production Compose overlay runs Redis with `--requirepass`, removes the
host port, and requires `REDIS_PASSWORD`.

---

## ⚖️ Judge worker variables

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `JUDGELOOM_API_URL` | `http://localhost:8000/api/v1/judge` | **Must include `/api/v1/judge`** |
| `JUDGELOOM_JUDGE_TOKEN` | required | Token printed once by `create_judge_token` |
| `JUDGELOOM_JUDGE_NAME` | required | Must match the judge record name |
| `WORKER_ALLOW_INSECURE_HTTP` | `false` | Development only; production must use HTTPS |
| `WORKER_LANGUAGES` | `PY3,CPP17` | Claimed language keys |
| `WORKER_CACHE_DIR` | `./worker-cache` | Persistent package cache |
| `WORKER_POLL_INTERVAL` | `2s` | Empty-claim poll delay |
| `WORKER_HEARTBEAT` | `10s` | Lease/heartbeat interval |
| `WORKER_SHADOW` | `false` | Use the shadow/replay lane |

Create a judge token:

```bash
python manage.py create_judge_token judge-worker-1
# The token is printed once; store it in JUDGELOOM_JUDGE_TOKEN.
```

The worker uses the **judge gateway** base URL, not the API root. A base URL of
`http://web:8000/api/v1` produces `404 /api/v1/register`; use
`http://web:8000/api/v1/judge`.

---

## 🧪 go-judge variables

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `GO_JUDGE_URL` | `http://localhost:5050` | Worker → go-judge REST endpoint |
| `GO_JUDGE_TOKEN` | empty | Worker bearer token |
| `GO_JUDGE_AUTH_TOKEN` | dev default in Compose | Compose-side shared secret; must match `GO_JUDGE_TOKEN` |

Compose starts go-judge with:

```text
-no-fallback -auth-token <GO_JUDGE_AUTH_TOKEN>
```

`/version` is public for health checks; execution endpoints require the bearer
token. Production removes the host port and keeps go-judge on the internal
`judge_net` only.

---

## 🌸 Flower and monitoring

| Variable | Notes |
| :--- | :--- |
| `FLOWER_BASIC_AUTH` | Required by production overlay, format `user:password` |
| `SENTRY_DSN` | Optional error monitoring |
| `JUDGELOOM_API_URL` | Production must be an HTTPS URL |

Staff can read queue and judge health from `GET /api/judge/metrics`; the API
requires a staff JWT.

---

## 🧾 Example development `.env`

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.development
DJANGO_SECRET_KEY=dev-only-change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=postgres://judgeloom:judgeloom@localhost:5432/judgeloom
POSTGRES_DB=judgeloom
POSTGRES_USER=judgeloom
POSTGRES_PASSWORD=judgeloom

REDIS_PASSWORD=dev-redis-password
REDIS_URL=redis://:dev-redis-password@localhost:6379/0
CELERY_BROKER_URL=redis://:dev-redis-password@localhost:6379/1
CHANNEL_LAYERS_URL=redis://:dev-redis-password@localhost:6379/2

JUDGELOOM_JUDGE_NAME=judge-worker-1
JUDGELOOM_JUDGE_TOKEN=replace-with-create_judge_token-output
GO_JUDGE_URL=http://localhost:5050
GO_JUDGE_TOKEN=dev-judge-token
```

> [!NOTE]
> The development `DJANGO_SECRET_KEY` above is rejected by production settings.
> That is intentional: production must use a unique generated key.

---

## 🧭 Next steps

- [Your first submission](first-submission.md)
- [Production deployment](../operations/deployment.md)
- [Troubleshooting](../operations/troubleshooting.md)
- [Security model](../architecture/security.md)

---

<div align="center">
  <sub>← <a href="quickstart.md">Quickstart</a> · <a href="../README.md">Documentation hub</a> · <a href="first-submission.md">First submission</a> →</sub>
</div>
