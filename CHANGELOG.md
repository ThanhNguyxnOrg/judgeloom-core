# Changelog

All notable changes to **JudgeLoom** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-17

### Added
- Initial scaffolding of the JudgeLoom platform — Django 5.1, Django Ninja, Channels, Celery, Pydantic v2.
- Domain apps: `accounts`, `contests`, `problems`, `submissions`, `judge`, `ratings`, `content`, `tags`, `tickets`, `organizations`.
- Service-layer architecture and `core.events` pub/sub bus.
- Native contest formats: ICPC, IOI, AtCoder, ECOO, Default.
- Health endpoints and baseline CI (lint, typecheck, tests).
- Community health files: `LICENSE` (AGPL-3.0), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`.
- GitHub issue templates (bug, feature, question), pull request template, `CODEOWNERS`, `FUNDING.yml`, `dependabot.yml`.
- CodeQL static analysis workflow.
- Release workflow that publishes a GitHub Release on every `v*.*.*` tag.
- `.editorconfig` and `.gitattributes` for consistent cross-platform formatting.

### Changed
- Hardened the CI workflow with explicit `permissions`, concurrency cancellation, and `workflow_dispatch`.
- Refreshed `README.md` badges and links to point at the canonical organization repository.

[Unreleased]: https://github.com/ThanhNguyxnOrg/judgeloom-core/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ThanhNguyxnOrg/judgeloom-core/releases/tag/v0.1.0
