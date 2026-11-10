# Kernelridge

Know what breaks before it breaks.

A local-first Python 3.11+ compatibility preflight prototype based on the
Kernelridge proposal. The upstream repository was empty; this implementation
does not include or claim to reuse a VCM Machines codebase.

## Quick start

```bash
python -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/kernelridge preflight --target examples/target.json --release examples/release.json
# Expected FAIL (exit 1): the release requires the unavailable v extension.
.venv/bin/kernelridge --output report.json preflight --target examples/target.json --release examples/compatible-release.json
.venv/bin/kernelridge experiment plan --catalog examples/catalog.json --budget-minutes 7
.venv/bin/kernelridge --output attestation.json report --input report.json
```

`vcm` is an alias for the CLI. Without installation, use `python -m kernelridge`.
Global `--output` precedes the command. Invalid input exits 2; detected
incompatibility or insufficient mandatory budget exits 1.

## Available workflows

- `discover`: collect local OS metadata. ISA and ABI remain unknown until supplied by verified inventory.
- `preflight --target FILE --release FILE`: check architecture, explicit ISA extension sets, exact ABI and library versions. Example JSON manifests are in `examples/`.
- `invalidate --before FILE --after FILE --evidence FILE`: compare revisions and flag affected evidence. Evidence input is a JSON list of records with `status`, `assumptions` (manifest paths), and optional `dependencies_complete`. Incomplete dependency coverage forces revalidation after any change.
- `experiment plan --catalog FILE --budget-minutes N`: reserve mandatory coverage, then rank optional experiments by information gain × severity × relevance / cost. An infeasible mandatory budget blocks the plan.
- `experiment run --binary FILE --timeout 10`: explicitly request a bounded, isolated 64-bit RISC-V static ELF smoke execution. Requires `qemu-riscv64`, `bwrap`, `prlimit`, and working unprivileged namespaces on Linux. No arbitrary shell commands, network, or host home mounts. Limits include wall time, CPU, memory, process count, and output size. Missing tools or execution failures yield UNKNOWN. This command runs one binary; it does not automatically execute a planned catalog.
- `report --input FILE`: wrap a JSON record with a canonical SHA-256 digest and approval requirement. This is an **unsigned** export, not a cryptographic attestation.

Reports never promote matching metadata to runtime PASS: static success yields
REVIEW, missing facts yield UNKNOWN, and mismatches yield FAIL. Emulation
observations have explicit scope and never establish physical validation. Library
comparisons currently use exact versions, not semantic ranges. ISA extensions
must be explicitly enumerated; ISA strings and implied extensions are not parsed.

## Development

```bash
python -m unittest discover -s tests -v
python -m pip wheel --no-deps --no-build-isolation . -w dist
```

Runtime has no third-party Python dependencies. CI checks Python 3.11–3.13.
Tests cover ISA/architecture/ABI failures, unknown inventory, conservative
invalidation, unaffected evidence reuse, mandatory budgets, and stable hashes.

## Scope and remaining work

This is an initial deterministic CLI foundation, not the complete v0.1 definition
of done in [the proposal](KERNELRIDGE.md). Records are explicit JSON files;
SQLite persistence, dependency graph traversal, ELF ABI/attribute extraction,
target-specific QEMU system images, physical-board validation, signed
attestations, AI diagnosis/remediation, API/dashboard/MCP integration, and
research benchmarks remain future work. No production deployment is performed.
The planner is a reproducible heuristic with no claimed optimality or measured
failure-detection guarantee.
