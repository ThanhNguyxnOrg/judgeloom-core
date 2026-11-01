[🏠 Project README](../../README.md) · [📚 Documentation](../README.md) · [Next: Configuration →](configuration.md)

# 🚀 Quickstart

Get JudgeLoom running locally in a few minutes. Choose **Docker Compose** for a
full stack, or **local Python** for a lightweight control plane.

> [!IMPORTANT]
> The example secrets are development defaults. Generate real values before
> exposing JudgeLoom to anyone else. See [Configuration](configuration.md).

---

## 🐳 Option A — Docker Compose (recommended)

### Prerequisites

- Docker Engine / Docker Desktop with Linux containers
- Docker Compose v2
- Git

### 1. Clone and configure

```bash
git clone https://github.com/ThanhNguyxnOrg/judgeloom-core.git
cd judgeloom-core

cp .env.example .env
```

Open `.env` and set at least:

```dotenv
DJANGO_SECRET_KEY=<generate a unique 50+ character key>
POSTGRES_PASSWORD=<random password>
REDIS_PASSWORD=<random url-safe password>
GO_JUDGE_AUTH_TOKEN=<random token>
JUDGELOOM_JUDGE_TOKEN=<token from create_judge_token>
JUDGELOOM_JUDGE_NAME=judge-worker-1
```

Generate a Django signing key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2. Start the stack

```bash
docker compose up -d --build postgres redis web go-judge
```

The development stack uses PostgreSQL when `DATABASE_URL` is set, and SQLite
when it is empty. Redis is password-protected by `REDIS_PASSWORD`; go-judge is
token-protected by `GO_JUDGE_AUTH_TOKEN`.

### 3. Initialize data

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_users
docker compose exec web python manage.py seed_languages
docker compose exec web python manage.py seed_problems
```

The development seed users use the password `judgeloom2025` unless you pass
`--password`. Change it for anything beyond local experimentation.

### 4. Check health

```bash
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready
```

Expected: `{"status": "ok", ...}`. The readiness check verifies the database.

### 5. Judge a submission

The control plane is running, but judging needs a package, a judge record, and
a worker. Follow [Your first submission](first-submission.md) for the complete
walkthrough.

> [!NOTE]
> The development Compose file publishes the web port on `0.0.0.0:8000` for
> convenience. The production overlay binds it to `127.0.0.1:8000`; put a TLS
> reverse proxy in front of it. See [Deployment](../operations/deployment.md).

---

## 🐍 Option B — Local Python

Use this path when you want the fastest edit/test loop. SQLite and in-memory
channels are used when `DATABASE_URL` is empty.

### Prerequisites

- Python 3.12+
- Git
- Docker (only for the real go-judge sandbox tests)

### Setup

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

pip install -r requirements/base.txt -r requirements/testing.txt

cp .env.example .env
# Leave DATABASE_URL empty for SQLite, or point it at PostgreSQL.
```

### Migrate, seed, and run

```bash
python manage.py migrate
python manage.py seed_users
python manage.py seed_languages
python manage.py seed_problems
python manage.py runserver
```

- API: <http://127.0.0.1:8000/api/>
- Swagger UI: <http://127.0.0.1:8000/api/docs>
- Liveness: <http://127.0.0.1:8000/api/health/live>
- Readiness: <http://127.0.0.1:8000/api/health/ready>

To judge submissions, start go-judge and a worker as described in
[Your first submission](first-submission.md).

---

## ✅ What should be running?

| Service | Local URL | Purpose |
| :--- | :--- | :--- |
| Django control plane | `http://127.0.0.1:8000` | API, auth, submissions, scoring |
| PostgreSQL | internal / `localhost:5432` | Primary data store |
| Redis | internal / `localhost:6379` | Cache, sessions, Celery, Channels |
| go-judge | internal / `127.0.0.1:5050` | Sandboxed execution |
| Judge worker | outbound only | Claims jobs and reports verdicts |

---

## 🧭 Next steps

1. [Configure](../getting-started/configuration.md) the environment properly.
2. [Submit your first solution](first-submission.md).
3. Learn the [architecture](../architecture/overview.md).
4. Read the [security model](../architecture/security.md) before deploying.

---

<div align="center">
  <sub>Trouble? See <a href="../operations/troubleshooting.md">Troubleshooting</a>.</sub>
</div>
