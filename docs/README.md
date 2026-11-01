<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="assets/logo.svg" />
    <img src="assets/logo.png" alt="JudgeLoom" width="96" />
  </picture>

  # 📚 JudgeLoom Documentation

  **Everything you need to run, extend, and operate JudgeLoom.**

  [![CI](https://img.shields.io/github/actions/workflow/status/ThanhNguyxnOrg/judgeloom-core/ci.yml?branch=master&style=for-the-badge&logo=githubactions&logoColor=white&label=CI)](https://github.com/ThanhNguyxnOrg/judgeloom-core/actions/workflows/ci.yml)
  [![License](https://img.shields.io/badge/license-AGPL--3.0-brightgreen.svg?style=for-the-badge)](../LICENSE)
  [![API-first](https://img.shields.io/badge/API-first-blueviolet.svg?style=for-the-badge)](reference/api.md)
</div>

> [!TIP]
> **New here?** Read the [Quickstart](getting-started/quickstart.md), then follow
> [Your first submission](getting-started/first-submission.md) to see the full
> control-plane → worker → sandbox flow.

---

## 🚀 Start here

| Goal | Read | Time |
| :--- | :--- | :---: |
| Get a local stack running | [Quickstart](getting-started/quickstart.md) | 5 min |
| Configure secrets and services | [Configuration](getting-started/configuration.md) | 10 min |
| Submit and watch a real verdict | [Your first submission](getting-started/first-submission.md) | 15 min |
| Understand the architecture | [Architecture overview](architecture/overview.md) | 10 min |
| Design a deployment | [Deployment guide](operations/deployment.md) | 20 min |
| Integrate with the API | [API reference](reference/api.md) | 10 min |
| Author a problem package | [Package authoring](judge/package-authoring.md) | 15 min |

---

## 🗺️ Documentation map

### 🏁 Getting started

- [Quickstart](getting-started/quickstart.md) — Docker Compose and local Python paths.
- [Configuration](getting-started/configuration.md) — every important environment variable.
- [Your first submission](getting-started/first-submission.md) — package, worker, JWT, verdict.

### 🏛️ Architecture

- [System overview](architecture/overview.md) — components, job lifecycle, data flow.
- [Security model](architecture/security.md) — trust boundaries, tokens, sandbox, deployment controls.

### 🛠️ Operations

- [Production deployment](operations/deployment.md) — Compose, TLS, backups, upgrades.
- [Troubleshooting](operations/troubleshooting.md) — the failures you will actually see.

### 🧪 Development

- [Testing and verification](development/testing.md) — Python, Go, sandbox, Docker, links.
- [Contributing guide](../CONTRIBUTING.md) — workflow, standards, and PR expectations.

### 📖 Reference

- [API reference](reference/api.md) — routes, auth, examples, errors.
- [Package format](reference/package-format.md) — manifest, cases, checkers, validators.
- [Glossary](reference/glossary.md) — the vocabulary used across the codebase.

### ⚖️ Judge internals

- [Judge protocol v1](judge/protocol-v1.md) — worker API contract.
- [Worker runbook](judge/worker.md) — configuration, languages, sandbox troubleshooting.
- [Package authoring](judge/package-authoring.md) — generator + model solution → ZIP.

### 🔬 Research archive

These notes are kept as design context for the project. They are intentionally
separate from the operational documentation above.

- [Research archive index](research/README.md) — historical context and caveats.
- [Open-source online judge landscape](research/open-source-online-judges.md) — DMOJ, CMS, DOMjudge, Hydro, and more.
- [Commercial OJ UX teardown](research/commercial-oj-ux-teardown.md) — product patterns from major judges.
- [Brand assets](assets/brand/README.md) — logo, mark, palette, and export guidance.

---

## 🧭 Reading paths

> [!NOTE]
> **Evaluating JudgeLoom?** Read [Architecture](architecture/overview.md) and
> [Security](architecture/security.md), then run the [Quickstart](getting-started/quickstart.md).
>
> **Deploying it?** Read [Configuration](getting-started/configuration.md) and
> [Production deployment](operations/deployment.md) before exposing the service.
>
> **Contributing?** Read [Development](development/testing.md) and the
> [Contributing guide](../CONTRIBUTING.md), then run the quality gates.
>
> **Setting a problem?** Read [Package authoring](judge/package-authoring.md) and
> [Package format](reference/package-format.md), then import the generated ZIP.

---

## 🔗 Project links

- [Project README](../README.md) — overview and quick start.
- [Security policy](../SECURITY.md) — private vulnerability reporting.
- [Code of Conduct](../CODE_OF_CONDUCT.md) — community expectations.
- [License](../LICENSE) — AGPL-3.0-or-later.
- [GitHub repository](https://github.com/ThanhNguyxnOrg/judgeloom-core) — source, issues, actions.

---

<div align="center">
  <sub>Documentation is part of the source. Keep links working when you change code.</sub>
</div>
