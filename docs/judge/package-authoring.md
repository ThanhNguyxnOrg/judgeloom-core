[🏠 Project README](../../README.md) · [📚 Documentation](../README.md) · [📦 Package format](../reference/package-format.md) · [🤖 Worker runbook](worker.md)

# Package Authoring

`judgeloom-package` builds an immutable, importable test package from a
Testlib-style generator, a model solution, and optional validator/checker
sources. Generation runs at authoring time inside go-judge; the judge only ever
sees static inputs and answers.

This keeps test data reproducible and avoids running a generator for every
submission.

## Workflow

Write a spec and the generator/solution sources, build the ZIP, then import it:

```bash
cd worker
go build -o judgeloom-package ./cmd/judgeloom-package

GO_JUDGE_URL=http://127.0.0.1:5050 \
GO_JUDGE_TOKEN=dev-judge-token \
./judgeloom-package \
  -spec ../problems/aplusb/package.json \
  -out ../problems/aplusb/aplusb.zip

cd ..
python manage.py import_problem_package aplusb problems/aplusb/aplusb.zip
```

`GO_JUDGE_TOKEN` must match the compose file's `GO_JUDGE_AUTH_TOKEN`
(`dev-judge-token` by default in development). If go-judge runs without a
token, omit `GO_JUDGE_TOKEN`. The CLI validates the token against a protected
endpoint before compiling anything. Run it against a local/authoring go-judge;
the production sandbox is not host-exposed.

## Spec

```json
{
  "schema": 1,
  "problem_code": "aplusb",
  "points": 100,
  "time_limit": 2.0,
  "memory_limit": 262144,
  "partial_score": false,
  "short_circuit": false,
  "checker": {"type": "exact"},
  "validator": {"type": "testlib", "source_file": "validator.cpp"},
  "generator": {"language": "CPP17", "source_file": "generator.cpp"},
  "solution": {"language": "CPP17", "source_file": "solution.cpp"},
  "cases": [
    {"id": "small-1", "args": ["1", "10"], "points": 20, "group": "small"},
    {"id": "large-1", "args": ["2", "100000"], "points": 80, "group": "large"}
  ],
  "groups": [
    {"id": "small", "points": 20, "mode": "sum"},
    {"id": "large", "points": 80, "mode": "sum"}
  ]
}
```

- `generator` and `solution` are required and support `PY3`/`CPP17`.
- `generator.args` are passed as `argv` to the generator. Testlib generators
  use `registerGen(argc, argv, 1)`, so deterministic args produce the same
  input on every build.
- `solution` is run on each generated input; its stdout becomes the case
  answer. It must finish with `AC` inside the problem limits.
- `checker` is `exact`, `testlib`, or `none`. `testlib` requires `source` or
  `source_file`. Interactive checkers are rejected because they cannot produce
  a static answer file.
- `validator` is optional. A Testlib validator reads the generated input from
  stdin and rejects the build on a non-zero exit.
- When a Testlib checker is present, the builder runs it against the model
  answer as a self-check.
- `source` and `source_file` are alternatives. Files are resolved relative to
  the spec directory and may not escape it.
- Omitted case points are distributed evenly from `points`; omitted groups
  produce one `default` sum group.
- The vendored Testlib header is available automatically:
  `#include "testlib.h"`.

Example generator:

```cpp
#include "testlib.h"
#include <cstdio>
#include <cstdlib>

int main(int argc, char **argv) {
    registerGen(argc, argv, 1);
    int a = atoi(argv[1]);
    int b = atoi(argv[2]);
    printf("%d %d\n", a, b);
    return 0;
}
```

Example solution:

```cpp
#include <iostream>

int main() {
    long long a = 0, b = 0;
    std::cin >> a >> b;
    std::cout << a + b << "\n";
    return 0;
}
```

## What the builder does

1. Compiles the generator once and runs it per case with the declared args.
2. Runs the validator on each generated input, when configured.
3. Compiles the solution once and runs it on each input to produce the answer.
4. Runs the Testlib checker against the model answer.
5. Writes `manifest.json`, `data/NN.in`, and `data/NN.ans` into a ZIP.

The manifest records the generator/solution language, source SHA-256, and case
args for provenance. Generator/solution source text is not embedded in the
package.

## Limits

| Limit | Value |
|---|---|
| Cases | 1–200 |
| Source per program | 256 KiB |
| Args per case | 32, each ≤256 bytes |
| Generated input / answer per case | 16 MiB |
| Total generated data | 255 MiB |
| Output ZIP | 64 MiB |
| Generator CPU time | 30 s |
| Problem time / memory | 0.1–60 s / 1 MiB–1 GiB |

These match the control plane's package import limits. A build that exceeds
them fails before publishing the ZIP; an existing output file is only replaced
after the whole build succeeds.

## Determinism and safety

- Generators must be deterministic for a given set of args. Do not read the
  clock or unseeded randomness.
- Generator, validator, checker, and solution all run in go-judge with CPU,
  memory, process, and output limits. The control plane never runs them.
- The generated ZIP is static; importing it does not execute the generator.
- Keep the spec and sources under version control next to the problem package.
- Import the result with `python manage.py import_problem_package`; see
  [Package format](../reference/package-format.md).
- Judge-time behavior is defined by [Protocol v1](protocol-v1.md).
