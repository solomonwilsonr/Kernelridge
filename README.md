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
| Check target vs. release compatibility (arch, ISA extensions, ABI, libraries); FAIL findings include a deterministic remediation hint | `preflight` |
| Flag evidence invalidated by a revision change, transitively across an explicit evidence dependency graph | `invalidate` |
| Plan experiments under a time budget (mandatory coverage first, then ranked by information gain × severity × relevance / cost) | `experiment plan` |
| Run a single sandboxed RISC-V static ELF smoke test | `experiment run` |
| Derive architecture/ABI/ISA-extension facts from a real ELF binary | `inspect` |
| Wrap a record with a canonical SHA-256 digest | `report` |
| Generate an Ed25519 keypair and sign/verify a report digest (via the system `openssl`) | `keygen`, `attest`, `verify` |
| Persist and query report history in a local SQLite store | `store save`/`list`/`show` |
| Serve a minimal read-only HTML/JSON dashboard over stored report history | `serve` |

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

# Wrap the report with a canonical SHA-256 digest (unsigned)
.venv/bin/kernelridge --output attestation.json report --input report.json

# Persist the report and list stored history
.venv/bin/kernelridge store save --input report.json --db .kernelridge/store.db
.venv/bin/kernelridge store list --db .kernelridge/store.db

# Derive facts from a real ELF binary instead of hand-authoring them
.venv/bin/kernelridge inspect --binary /path/to/release-binary

# Sign a report digest with a local Ed25519 key (requires openssl on PATH)
.venv/bin/kernelridge keygen --private key.pem --public key.pub
.venv/bin/kernelridge attest --input report.json --private key.pem > signed.json
.venv/bin/kernelridge verify --attestation signed.json --public key.pub
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
semantic ranges. Each `FAIL` finding carries a `remediation` field from a
small, deterministic, rule-keyed lookup table (architecture/ISA/ABI/library
mismatch classes) — a heuristic hint, not AI-assisted diagnosis.

### `invalidate --before FILE --after FILE --evidence FILE`

Compares a before/after revision pair and flags evidence records affected by
the change. `--evidence` is a JSON list of records with `status`,
`assumptions` (manifest paths the record depends on), optional
`dependencies_complete`, and optional `claim_id`/`depends_on` fields to form
an explicit evidence dependency graph. Incomplete dependency coverage forces
revalidation regardless of whether tracked assumptions changed, and
invalidation propagates transitively: a record that `depends_on` an
invalidated claim is itself flagged, to a fixpoint. Evidence lists without
`claim_id`/`depends_on` behave exactly as before.

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

### `inspect --binary FILE`

Parses a real ELF binary's header with manual `struct.unpack` (no
`readelf`/`pyelftools` dependency) and emits a machine/artifact-shaped JSON
fragment — `architecture`, and for 64-bit RISC-V binaries, the
`lp64`/`lp64f`/`lp64d`/`lp64q` ABI derived from `e_flags`, plus best-effort
ISA extensions parsed from a `.riscv.attributes` arch string when the section
is present. Facts it cannot determine (e.g. ISA extensions with no attributes
section) are left `null`, never guessed. The output feeds directly into
`preflight`.

### `keygen --private FILE --public FILE`

Generates a local Ed25519 keypair by shelling out to the system `openssl`
(`genpkey`/`pkey`). Adds no third-party Python crypto dependency. If
`openssl` is not on `PATH`, reports `signed: false` with a reason and writes
no key files.

### `attest --input FILE [--private FILE]`

Like `report`, but if `--private` is given and `openssl` is available, signs
the canonical digest with that Ed25519 key (`signed: true`, `signature`,
`algorithm: ed25519`). If `openssl` is missing or signing fails, it degrades
to the same unsigned export as `report`, with an explicit `note` — it never
claims to be signed when it isn't.

### `verify --attestation FILE --public FILE`

Verifies an `attest`-produced record's signature against a public key.
Returns `{"sha256": ..., "valid": true|false}`; invalid attestations exit 1.

### `store save|list|show`

Persists `preflight`/`attest` reports in a local SQLite database keyed by
their canonical digest (`store save --input FILE --db PATH`), lists stored
history with optional `--machine-revision`/`--artifact-revision` filters
(`store list --db PATH`), or fetches one by digest (`store show --sha256 HEX
--db PATH`). The database path is always explicit (`--db`, default
`.kernelridge/store.db`); nothing is written outside it.

### `serve --db PATH [--port N] [--bind HOST]`

Serves a minimal, read-only dashboard (stdlib `http.server` only — no web
framework) over a SQLite store built by `store save`: an HTML index at `/`,
a JSON listing at `/reports`, and a single record at `/reports/<sha256>`.
No write endpoints.

## Development

```bash
python -m unittest discover -s tests -v
python -m pip wheel --no-deps --no-build-isolation . -w dist
```

CI checks Python 3.11–3.13. Tests cover ISA/architecture/ABI/library
mismatches and their remediation hints, unknown inventory, conservative and
transitive invalidation, unaffected-evidence reuse, mandatory experiment
budgets, stable report hashes, ELF header parsing (synthetic x86_64 and
RISC-V fixtures), SQLite store round-trips, the signed-attestation degrade
path (and a real openssl round-trip when available), and the read-only
dashboard over an ephemeral HTTP server.

## Scope and limitations

This is an initial deterministic CLI foundation, not the full v0.1 definition
of done described in [the proposal](KERNELRIDGE.md). Implemented, within a
stdlib-only, no-third-party-dependency constraint:

- SQLite persistence (`store`) and evidence dependency graph traversal
  (`invalidate`'s `depends_on`)
- ELF header parsing and best-effort ABI/ISA-extension extraction (`inspect`)
- Optional Ed25519-signed attestations via the system `openssl` CLI
  (`keygen`/`attest`/`verify`), degrading gracefully when `openssl` is absent
- Deterministic, rule-keyed remediation hints on `FAIL` findings
- A minimal read-only dashboard over stored report history (`serve`)

Explicitly **not** implemented, and not attempted by the features above —
these require infrastructure (real target hardware, large downloads,
external services) outside a local-first, dependency-free CLI prototype:

- Target-specific QEMU system images and physical-board validation
- True AI-assisted diagnosis or remediation (the remediation hints above are
  a fixed lookup table, not a model)
- A writable API, broader dashboard functionality, or MCP integration
- Research benchmarks and measured failure-detection guarantees

The experiment planner is a reproducible heuristic; it makes no claim of
optimality. No production deployment is performed by this tool.

## Contributing

Issues and pull requests are welcome. Please include tests for any behavior
change — `python -m unittest discover -s tests -v` should pass before
submitting.
