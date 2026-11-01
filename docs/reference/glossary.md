[🏠 Project README](../../README.md) · [📚 Documentation](../README.md) · [← Package format](package-format.md)

# 📖 Glossary

The vocabulary used across JudgeLoom source, API, and documentation.

| Term | Meaning |
| :--- | :--- |
| **Control plane** | Django application that owns identity, problems, contests, submissions, scoring, and package metadata. It never runs participant code. |
| **Judge worker** | Go process that pulls jobs, caches packages, runs code through go-judge, and reports per-case results. |
| **go-judge** | Sandbox execution service used by the worker. It runs with host-level privileges and must be treated as trusted infrastructure. |
| **Package** | Immutable, SHA-256-addressed ZIP containing `manifest.json` and test data. |
| **Manifest** | JSON inside a package describing cases, groups, points, checker, validator, and limits. |
| **Case** | One input/answer pair with points and an optional group. |
| **Group** | Subtask over one or more cases, scored with `sum` or `min` and capped at its points. |
| **Checker** | Program that compares participant output with the reference answer. Types: `exact`, `testlib`, `interactive`, `none`. |
| **Validator** | Trusted Testlib program that checks whether a generated/static input is well-formed. |
| **Generator** | Trusted program used at **authoring time** to produce static inputs; it is not run per submission. |
| **Interactor** | Program that communicates with an interactive participant and emits a verdict. |
| **Submission** | User source plus result, points, metrics, and visibility. |
| **Run** | Non-scoring execution with custom stdin; excluded from statistics and scored lists. |
| **JudgeJob** | Lease/ownership record connecting a submission (or run) to a worker. |
| **Lease** | Time-bounded claim on a job; expired leases can be retried up to `max_attempts`. |
| **Judge** | Worker record with a hashed token, capabilities, heartbeat, and online state. |
| **Shadow job** | Non-scoring replay of a submission, optionally pinned to one judge. |
| **Contest** | Timed event with participation, freeze, scoring format, and optional rating. |
| **Participation** | A user’s live or virtual membership in a contest. |
| **Freeze** | Scoreboard window where public rankings hide submissions after the freeze time. |
| **Elo-MMR** | Rating algorithm used for historical rating updates. |
| **Organization** | Group used to scope private problems/posts and membership-based visibility. |
| **Package hash** | SHA-256 identity of a package; used for cache verification and stale-data rejection. |
| **Manifest hash** | Per-case SHA-256 values stored to detect corrupted/updated case files. |
| **Source-only repo** | This repository intentionally excludes local `.env`, virtualenvs, databases, media, and generated artifacts. |
| **Judge gateway** | Worker-only API under `/api/v1/judge/`. The base URL must include `/judge`. |

---

## 🔗 Related documentation

- [Architecture overview](../architecture/overview.md)
- [Package format](package-format.md)
- [Judge protocol v1](../judge/protocol-v1.md)
- [API reference](api.md)

---

<div align="center">
  <sub>← <a href="package-format.md">Package format</a> · <a href="../README.md">Documentation hub</a> · <a href="../../README.md">Project README</a> →</sub>
</div>
