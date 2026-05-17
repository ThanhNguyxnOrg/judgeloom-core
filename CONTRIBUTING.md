# Contributing to JudgeLoom

First off — thanks for taking the time to contribute! 🎉
This document outlines the workflow, conventions, and standards we follow so that everyone has a smooth experience working on JudgeLoom.

---

## Table of contents

- [Code of conduct](#code-of-conduct)
- [Ways to contribute](#ways-to-contribute)
- [Development setup](#development-setup)
- [Branching strategy](#branching-strategy)
- [Commit message convention](#commit-message-convention)
- [Pull request workflow](#pull-request-workflow)
- [Coding standards](#coding-standards)
- [Testing](#testing)
- [Reporting bugs & requesting features](#reporting-bugs--requesting-features)
- [Security issues](#security-issues)

---

## Code of conduct

This project adheres to the [Contributor Covenant Code of Conduct](./CODE_OF_CONDUCT.md). By participating you are expected to uphold this code.

---

## Ways to contribute

- 🐛 **Report bugs** via the [Bug report](https://github.com/ThanhNguyxnOrg/judgeloom-core/issues/new?template=bug_report.yml) template.
- ✨ **Propose features** via the [Feature request](https://github.com/ThanhNguyxnOrg/judgeloom-core/issues/new?template=feature_request.yml) template.
- 📚 **Improve documentation** — even small typo fixes are welcome.
- 🧪 **Add tests** that cover untested code paths.
- 💻 **Submit code** for open issues, especially ones labelled `good first issue` or `help wanted`.

---

## Development setup

JudgeLoom targets **Python 3.12+**, **PostgreSQL 16+**, and **Redis 7+**.

```bash
# 1. Clone and enter the repo
git clone https://github.com/ThanhNguyxnOrg/judgeloom-core.git
cd judgeloom-core

# 2. Create a virtual environment and install dev dependencies
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\activate
make install

# 3. Configure environment variables
cp .env.example .env

# 4. Apply migrations and seed data
make migrate
make seed

# 5. Install pre-commit hooks (recommended)
pre-commit install
```

Common make targets — see `make help` for the full list:

| Target | Description |
| :-- | :-- |
| `make run` | Start the Django dev server |
| `make test` | Run the full pytest suite |
| `make lint` | Run ruff lint checks |
| `make format` | Auto-format the codebase with ruff |
| `make typecheck` | Run mypy |
| `make check` | Lint + typecheck + test (the CI gate) |

---

## Branching strategy

We use a simple trunk-based flow:

- `master` — always deployable. Direct commits are discouraged.
- `feat/<short-description>` — new features
- `fix/<short-description>` — bug fixes
- `docs/<short-description>` — documentation only
- `chore/<short-description>` — tooling, deps, CI
- `refactor/<short-description>` — non-functional changes

Keep branches small and focused. One PR ≈ one logical change.

---

## Commit message convention

We follow **[Conventional Commits](https://www.conventionalcommits.org/)**:

```
<type>(<scope>): <short summary>

<optional body>

<optional footer>
```

**Allowed types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.

**Examples:**

```
feat(submissions): add real-time progress streaming via channels
fix(accounts): prevent duplicate email registration race
docs(readme): clarify Redis setup steps
ci: pin actions/checkout to v4
```

Breaking changes — append `!` after the type/scope **and** include a `BREAKING CHANGE:` footer:

```
feat(api)!: rename submissions endpoint to /v2/submissions

BREAKING CHANGE: clients targeting /submissions must migrate to /v2/submissions.
```

---

## Pull request workflow

1. **Fork** the repo and create a topic branch from `master`.
2. Make your changes, **add or update tests**, and keep commits clean.
3. Run the full quality gate locally:
   ```bash
   make check
   ```
4. Push the branch and open a PR against `master`. Fill out the PR template completely.
5. CI must pass. Address review feedback by pushing follow-up commits — the maintainer will squash-merge on approval.

**PR sizing tips:** under ~400 lines of diff is ideal for fast review. Split larger work into multiple PRs whenever possible.

---

## Coding standards

- **Python style** — enforced by [ruff](https://docs.astral.sh/ruff/). Run `make format` before committing.
- **Type hints** — required for all new code. We use `from __future__ import annotations` consistently. Mypy in `strict` mode is part of CI.
- **Service layer** — keep models and views thin; put business logic in `apps/<app>/services/`.
- **Events** — apps communicate across boundaries via the `core.events` pub/sub mechanism, not direct imports.
- **Migrations** — always commit Django migrations alongside model changes.
- **Docstrings** — public functions, classes, and modules need a short docstring describing intent.
- **No secrets** — never commit `.env` files, API keys, or credentials. Use `.env.example` for new variables.

---

## Testing

- Tests live under `tests/` (and per-app under `apps/<app>/tests/`).
- We use **pytest** with **pytest-django**.
- Aim for ≥80 % coverage on new code (`make test-cov`).
- Mark slow or external-service-dependent tests with `@pytest.mark.slow` or `@pytest.mark.integration`.

```bash
make test           # full suite
pytest tests/path   # a subset
pytest -m "not slow"
```

---

## Reporting bugs & requesting features

Please use the issue templates linked in the repo's [Issues tab](https://github.com/ThanhNguyxnOrg/judgeloom-core/issues/new/choose). Provide enough context (versions, reproduction steps, logs) for a maintainer to act without going back-and-forth.

---

## Security issues

**Do not** open public issues for security vulnerabilities. Follow the process documented in [`SECURITY.md`](./SECURITY.md).

---

Thanks again for contributing! 💜
