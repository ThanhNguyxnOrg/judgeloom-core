[🏠 Project README](../../README.md) · [📚 Documentation](../README.md) · [← API reference](api.md) · [Next: Glossary →](glossary.md)

# 📦 Package format

A problem package is an immutable ZIP containing a `manifest.json` and test
data. The package SHA-256 is its identity: workers verify it, cache it, and
report it with every result.

For the worker wire contract, see
[Protocol v1 → Package manifest](../judge/protocol-v1.md#package-manifest).
For the authoring CLI, see [Package authoring](../judge/package-authoring.md).

---

## 🗂️ Archive layout

```text
aplusb.zip
├── manifest.json
└── data/
    ├── 01.in
    ├── 01.ans
    ├── 02.in
    └── 02.ans
```

The importer rejects absolute paths, `..` traversal, symlinks, duplicate case
stems, oversized archives, and too many cases.

---

## 🧾 Manifest

```json
{
  "schema": 1,
  "problem_code": "aplusb",
  "time_limit": 2.0,
  "memory_limit": 262144,
  "partial_score": false,
  "short_circuit": false,
  "checker": {"type": "exact"},
  "validator": {"type": "testlib", "source": "..."},
  "cases": [
    {
      "id": "01",
      "input": "data/01.in",
      "answer": "data/01.ans",
      "input_sha256": "<sha256>",
      "answer_sha256": "<sha256>",
      "points": 100,
      "group": "default"
    }
  ],
  "groups": [{"id": "default", "points": 100, "mode": "sum"}]
}
```

| Field | Meaning |
| :--- | :--- |
| `schema` | Manifest schema; currently `1` |
| `problem_code` | Problem code this package belongs to |
| `time_limit` / `memory_limit` | Package metadata; runtime limits come from the problem |
| `partial_score` | Allows `PT` and subtask scoring when true |
| `short_circuit` | Stops after the first failing case when true |
| `checker` | `exact`, `testlib`, `interactive`, or `none` |
| `validator` | Optional Testlib input validator |
| `cases` | Ordered cases with files, hashes, points, group |
| `groups` | Group scoring mode `sum` or `min`, capped by group points |

The server recomputes case/group points from the immutable manifest; worker
totals are not authoritative.

---

## ⚖️ Checkers

| Type | Behavior |
| :--- | :--- |
| `exact` | Normalized stdout comparison |
| `testlib` | Inline Testlib checker compiled in go-judge |
| `interactive` | Two-command interactor/participant pipe run |
| `none` | Always accepts (`AC`) |

Testlib sources can `#include "testlib.h"`; the vendored header is compiled into
the sandbox automatically. Interactive packages need static input/answer files
and an inline interactor source. The generator CLI rejects interactive packages
because it cannot produce a static answer from a model solution.

---

## 🧪 Validators

A Testlib validator is optional:

```json
"validator": {"type": "testlib", "source": "..."}
```

Validators run on each input before the participant. The worker compiles once
and rejects invalid input as a package/judge error, never as a participant
wrong answer.

---

## 🔢 Limits and validation

The importer enforces:

| Limit | Value |
| :--- | :--- |
| Cases | 200 |
| Archive | 64 MiB |
| Uncompressed data | 256 MiB |
| Inline checker/validator source | 256 KiB |
| Case/group points | finite, non-negative, ≤1,000,000 |

Additional rules:

- at least one `.in`/`.out` or `.ans` pair,
- manifest cases must reference existing files,
- case groups must be defined (or the default group),
- `sum`/`min` are the only group modes.

---

## 📥 Import and activation

```bash
python manage.py import_problem_package aplusb aplusb.zip
```

- The import is content-addressed; re-importing the same bytes is idempotent.
- Each problem has one active package; old versions remain available for
  queued jobs and rejudges.
- Activation does not automatically rejudge old submissions; run an explicit
  rejudge when you intend to.

---

## 🧬 Authoring with generators

`judgeloom-package` builds a **static** package from a Testlib generator,
optional validator, and model solution:

```bash
cd worker
GO_JUDGE_URL=http://localhost:5050 GO_JUDGE_TOKEN=dev-judge-token \
  go run ./cmd/judgeloom-package -spec package.json -out aplusb.zip
```

The generated ZIP contains static inputs/answers; generators do not run at
judge time. See [Package authoring](../judge/package-authoring.md) for the spec
format and limits.

---

## 🔗 Related documentation

- [Package authoring](../judge/package-authoring.md)
- [Judge protocol v1](../judge/protocol-v1.md)
- [Worker runbook](../judge/worker.md)
- [API reference](api.md)

---

<div align="center">
  <sub>← <a href="api.md">API reference</a> · <a href="../README.md">Documentation hub</a> · <a href="glossary.md">Glossary</a> →</sub>
</div>
