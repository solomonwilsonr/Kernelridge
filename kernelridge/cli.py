import argparse
import json
import platform
from pathlib import Path

from .core import digest, invalidate, plan, preflight
from .lab import run


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
    args = parser.parse_args()
    try:
        if args.command == "discover":
            result = {"id": platform.node() or "local", "architecture": {"riscv64": "riscv64", "aarch64": "arm64"}.get(platform.machine(), platform.machine()), "kernel": platform.release(), "isa_extensions": None, "abi": None, "libraries": {}, "source": "local OS; ISA and ABI require verified inventory"}
        elif args.command == "preflight":
            result = preflight(load(args.target), load(args.release))
        elif args.command == "invalidate":
            result = invalidate(load(args.evidence), load(args.before), load(args.after))
        elif args.command == "experiment":
            result = plan(load(args.catalog), args.budget_minutes) if args.mode == "plan" else run(args.binary, args.timeout)
        else:
            record = load(args.input)
            result = {"report": record, "sha256": digest(record), "signed": False, "approval_required": True}
        encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            Path(args.output).write_text(encoded)
        else:
            print(encoded, end="")
        return 1 if result.get("decision") == "FAIL" or result.get("status") == "BLOCKED" else 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.exit(2, f"kernelridge: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
