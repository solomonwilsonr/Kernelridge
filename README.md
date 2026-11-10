<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-white.png">
    <img src="assets/logo.png" alt="Kernelridge logo" width="420">
  </picture>
</p>

# Kernelridge

**Know what breaks before it breaks.**

Kernelridge is a local-first, dependency-free compatibility preflight CLI for
Python 3.11+. It checks a target system's architecture, ISA extensions, ABI,
and library versions against what a release requires — before you deploy it —
and it is explicit about what it can and cannot verify.

> This is an independent implementation based on the public
> [Kernelridge proposal](KERNELRIDGE.md). The upstream VCM Machines repository
> referenced by that proposal was empty; this project does not include or
> claim to reuse any VCM Machines code.

## Why Kernelridge

Most compatibility checks either rubber-stamp a deploy because the metadata
*looks* right, or fail silently and let you find out at runtime. Kernelridge
takes a stricter stance:

- **No optimistic PASS.** A static match between target and release metadata
  is reported as `REVIEW`, never `PASS` — only a real runtime check earns that.
- **Missing data is `UNKNOWN`, not assumed-fine.** If ISA extensions or ABI
  aren't in verified inventory, Kernelridge says so instead of guessing.
- **Mismatches are `FAIL`**, with the specific missing extension, ABI, or
  library version called out.
- **Evidence invalidation is conservative.** When a revision changes anything
  an evidence record depended on — or dependency coverage is incomplete — that
  evidence is flagged for revalidation rather than silently reused.

## Features

| Capability | Command |
|---|---|
| Collect local OS/architecture metadata | `discover` |
| Check target vs. release compatibility (arch, ISA extensions, ABI, libraries) | `preflight` |
| Flag evidence invalidated by a revision change | `invalidate` |
| Plan experiments under a time budget (mandatory coverage first, then ranked by information gain × severity × relevance / cost) | `experiment plan` |
| Run a single sandboxed RISC-V static ELF smoke test | `experiment run` |
| Wrap a record with a canonical SHA-256 digest | `report` |

## Installation

Requires Python 3.11 or later. No third-party runtime dependencies.

```bash
python -m venv .venv
.venv/bin/python -m pip install .
```

Both `kernelridge` and the alias `vcm` are installed as console scripts. To run
without installing, use `python -m kernelridge` instead.

## Quick start

```bash
# A release that requires the unavailable "v" (vector) extension: exit 1 (FAIL)
.venv/bin/kernelridge preflight \
  --target examples/target.json --release examples/release.json

# A compatible release, writing the result to report.json
.venv/bin/kernelridge --output report.json preflight \
  --target examples/target.json --release examples/compatible-release.json

# Plan experiments within a 7-minute budget
.venv/bin/kernelridge experiment plan \
  --catalog examples/catalog.json --budget-minutes 7

# Wrap the report with a canonical SHA-256 digest
.venv/bin/kernelridge --output attestation.json report --input report.json
```

Notes:

- `--output` is a **global** flag and must precede the subcommand.
- Exit codes: `0` success, `1` incompatibility detected / mandatory budget
  infeasible, `2` invalid input.

## Commands

### `discover`

Collects local OS and architecture metadata. ISA extensions and ABI are left
`null` until supplied by verified inventory — Kernelridge will not infer them
from the running kernel.

### `preflight --target FILE --release FILE`

Checks architecture, explicit ISA extension sets, exact ABI, and library
versions. `--target` and `--release` are JSON manifests (see `examples/`).
ISA extensions must be explicitly enumerated — ISA strings and implied
extensions are not parsed — and library comparisons use exact versions, not
semantic ranges.

### `invalidate --before FILE --after FILE --evidence FILE`

Compares a before/after revision pair and flags evidence records affected by
the change. `--evidence` is a JSON list of records with `status`,
`assumptions` (manifest paths the record depends on), and optional
`dependencies_complete`. Incomplete dependency coverage forces revalidation
regardless of whether tracked assumptions changed.

### `experiment plan --catalog FILE --budget-minutes N`

Reserves mandatory coverage first, then ranks optional experiments by
information gain × severity × relevance / cost. An infeasible mandatory
budget blocks the plan (`BLOCKED`).

### `experiment run --binary FILE [--timeout SECONDS]`

Explicitly authorizes one bounded, isolated 64-bit RISC-V static ELF smoke
execution. Requires `qemu-riscv64`, `bwrap`, `prlimit`, and working
unprivileged namespaces on Linux. No arbitrary shell commands, network access,
or host home mounts are permitted. Wall time, CPU, memory, process count, and
output size are all bounded. Missing tools or execution failures resolve to
`UNKNOWN` rather than a false pass. This runs a single binary; it does not
execute a planned catalog automatically.

### `report --input FILE`

Wraps a JSON record with a canonical SHA-256 digest and an
`approval_required` flag. This is an **unsigned** export, not a cryptographic
attestation.

## Development

```bash
python -m unittest discover -s tests -v
python -m pip wheel --no-deps --no-build-isolation . -w dist
```

CI checks Python 3.11–3.13. Tests cover ISA/architecture/ABI mismatches,
unknown inventory, conservative invalidation, unaffected-evidence reuse,
mandatory experiment budgets, and stable report hashes.

## Scope and limitations

This is an initial deterministic CLI foundation, not the full v0.1 definition
of done described in [the proposal](KERNELRIDGE.md). Explicitly **not**
implemented yet:

- SQLite persistence and dependency graph traversal
- ELF ABI/attribute extraction (ISA/ABI facts must be supplied, not inferred)
- Target-specific QEMU system images and physical-board validation
- Signed (vs. digest-only) attestations
- AI-assisted diagnosis or remediation
- API, dashboard, and MCP integrations
- Research benchmarks and measured failure-detection guarantees

The experiment planner is a reproducible heuristic; it makes no claim of
optimality. No production deployment is performed by this tool.

## Contributing

Issues and pull requests are welcome. Please include tests for any behavior
change — `python -m unittest discover -s tests -v` should pass before
submitting.
