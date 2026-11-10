import argparse
import json
import platform
from pathlib import Path

from .core import digest, invalidate, plan, preflight
from .lab import run
from . import store as store_module
from .elf import inspect as elf_inspect
from . import attest as attest_module


def load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description="Kernelridge evidence-aware compatibility preflight")
    parser.add_argument("--output", help="Write JSON to this file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover", help="Collect local OS and architecture; unknown facts remain null")
    pre = sub.add_parser("preflight")
    pre.add_argument("--target", required=True)
    pre.add_argument("--release", required=True)
    inv = sub.add_parser("invalidate")
    inv.add_argument("--before", required=True)
    inv.add_argument("--after", required=True)
    inv.add_argument("--evidence", required=True)
    exp = sub.add_parser("experiment")
    modes = exp.add_subparsers(dest="mode", required=True)
    planning = modes.add_parser("plan")
    planning.add_argument("--catalog", required=True)
    planning.add_argument("--budget-minutes", type=float, required=True)
    execution = modes.add_parser("run", help="Explicitly authorize one isolated static RISC-V smoke test")
    execution.add_argument("--binary", required=True)
    execution.add_argument("--timeout", type=int, default=10)
    report = sub.add_parser("report")
    report.add_argument("--input", required=True)
    inspect = sub.add_parser("inspect", help="Derive a machine/artifact JSON fragment from a real ELF binary")
    inspect.add_argument("--binary", required=True)
    keygen = sub.add_parser("keygen", help="Generate a local Ed25519 keypair for signing attestations (requires openssl)")
    keygen.add_argument("--private", required=True)
    keygen.add_argument("--public", required=True)
    attest = sub.add_parser("attest", help="Wrap a record with its canonical digest and an optional Ed25519 signature")
    attest.add_argument("--input", required=True)
    attest.add_argument("--private", help="Sign with this Ed25519 private key; omitted or unavailable yields an unsigned export")
    verify = sub.add_parser("verify", help="Verify an attestation's signature against a public key")
    verify.add_argument("--attestation", required=True)
    verify.add_argument("--public", required=True)
    store = sub.add_parser("store", help="Persist and query preflight reports in a local SQLite store")
    store_modes = store.add_subparsers(dest="store_mode", required=True)
    store_save = store_modes.add_parser("save")
    store_save.add_argument("--input", required=True)
    store_save.add_argument("--db", default=store_module.DEFAULT_PATH)
    store_list = store_modes.add_parser("list")
    store_list.add_argument("--db", default=store_module.DEFAULT_PATH)
    store_list.add_argument("--machine-revision")
    store_list.add_argument("--artifact-revision")
    store_show = store_modes.add_parser("show")
    store_show.add_argument("--sha256", required=True)
    store_show.add_argument("--db", default=store_module.DEFAULT_PATH)
    serve = sub.add_parser("serve", help="Serve a minimal, read-only HTML/JSON dashboard over a stored report history")
    serve.add_argument("--db", default=store_module.DEFAULT_PATH)
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--bind", default="127.0.0.1")
    args = parser.parse_args()
    if args.command == "serve":
        from .dashboard import run_forever
        print(f"kernelridge dashboard listening on http://{args.bind}:{args.port} (Ctrl+C to stop)")
        run_forever(args.db, args.port, args.bind)
        return 0
    try:
        if args.command == "discover":
            result = {"id": platform.node() or "local", "architecture": {"riscv64": "riscv64", "aarch64": "arm64"}.get(platform.machine(), platform.machine()), "kernel": platform.release(), "isa_extensions": None, "abi": None, "libraries": {}, "source": "local OS; ISA and ABI require verified inventory"}
        elif args.command == "preflight":
            result = preflight(load(args.target), load(args.release))
        elif args.command == "invalidate":
            result = invalidate(load(args.evidence), load(args.before), load(args.after))
        elif args.command == "experiment":
            result = plan(load(args.catalog), args.budget_minutes) if args.mode == "plan" else run(args.binary, args.timeout)
        elif args.command == "report":
            record = load(args.input)
            result = {"report": record, "sha256": digest(record), "signed": False, "approval_required": True}
        elif args.command == "inspect":
            result = elf_inspect(args.binary)
        elif args.command == "keygen":
            result = attest_module.keygen(args.private, args.public)
        elif args.command == "attest":
            record = load(args.input)
            key_digest = digest(record)
            signature = attest_module.sign(key_digest, args.private) if args.private else None
            result = {"report": record, "sha256": key_digest, "signed": signature is not None, "signature": signature,
                      "algorithm": "ed25519" if signature is not None else None, "approval_required": True}
            if args.private and signature is None:
                result["note"] = "openssl unavailable or signing failed; export is unsigned"
        elif args.command == "verify":
            attestation = load(args.attestation)
            valid = bool(attestation.get("signed")) and bool(attestation.get("signature")) and attest_module.verify(
                attestation.get("sha256"), attestation.get("signature"), args.public)
            result = {"sha256": attestation.get("sha256"), "valid": valid}
        else:
            if args.store_mode == "save":
                result = store_module.save(load(args.input), args.db)
            elif args.store_mode == "list":
                result = {"reports": store_module.list_reports(args.db, args.machine_revision, args.artifact_revision)}
            else:
                result = store_module.show(args.sha256, args.db)
        encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            Path(args.output).write_text(encoded)
        else:
            print(encoded, end="")
        return 1 if result.get("decision") == "FAIL" or result.get("status") == "BLOCKED" or result.get("valid") is False else 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.exit(2, f"kernelridge: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
