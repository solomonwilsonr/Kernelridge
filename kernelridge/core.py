"""Deterministic checks and conservative evidence handling; no model required."""
import hashlib
import json
import math


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate(value, kind):
    if not isinstance(value, dict):
        raise ValueError(f"{kind} must be an object")
    for key in ("id", "architecture"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ValueError(f"{kind}.{key} must be a nonempty string")
    for key in ("isa_extensions", "required_extensions"):
        if value.get(key) is not None and (not isinstance(value[key], list) or any(not isinstance(x, str) for x in value[key])):
            raise ValueError(f"{key} must be a list of strings")
    if "libraries" in value and (not isinstance(value["libraries"], dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value["libraries"].items())):
        raise ValueError("libraries must map names to exact version strings")
    return value


def flatten(value, prefix=""):
    result = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            result.update(flatten(item, path))
        else:
            result[path] = item
    return result


def changes(before, after):
    a, b = flatten(before), flatten(after)
    return sorted(k for k in a.keys() | b.keys() if (k in a) != (k in b) or a.get(k) != b.get(k))


def invalidate(evidence, before, after):
    changed = changes(before, after)
    result = [dict(record) for record in evidence]
    invalidated = [False] * len(result)
    by_claim = {item["claim_id"]: i for i, item in enumerate(result) if "claim_id" in item}
    for i, item in enumerate(result):
        assumptions = item.get("assumptions")
        affected = not assumptions or any(c == a or c.startswith(a + ".") or a.startswith(c + ".") for c in changed for a in assumptions)
        # Unknown dependency coverage cannot justify reuse after a change.
        if changed and (affected or not item.get("dependencies_complete", False)):
            invalidated[i] = True
    # Transitive propagation: a record that depends_on an invalidated claim is itself invalidated.
    settled = False
    while not settled:
        settled = True
        for i, item in enumerate(result):
            if invalidated[i]:
                continue
            if any(invalidated[by_claim[dep]] for dep in item.get("depends_on") or [] if dep in by_claim):
                invalidated[i] = True
                settled = False
    for i, item in enumerate(result):
        if invalidated[i]:
            item["status"] = "POTENTIALLY_INVALIDATED"
    return {"changed_paths": changed, "evidence": result}


# Deterministic, rule-keyed remediation lookup table -- a heuristic hint, not AI/ML diagnosis.
REMEDIATION_HINTS = {
    "architecture": "Architectures differ: build or select a release targeting the machine's actual architecture, or correct the inventory if it is wrong.",
    "isa_extensions": "The release requires ISA extensions the machine does not expose: verify the machine's ISA inventory or select/build a release that does not require them.",
    "abi": "ABI strings differ: rebuild the release for the machine's ABI, or correct the inventory if it is wrong.",
}
DEFAULT_LIBRARY_REMEDIATION = "Library version does not match: install the required version on the machine, or rebuild the release against the machine's installed version."


def remediation_hint(rule):
    if rule in REMEDIATION_HINTS:
        return REMEDIATION_HINTS[rule]
    if rule.startswith("library."):
        return DEFAULT_LIBRARY_REMEDIATION
    return "Compatibility constraint not satisfied; review required vs observed values."


def preflight(machine, artifact):
    validate(machine, "machine")
    validate(artifact, "artifact")
    findings = []

    def check(rule, expected, actual, compatible=None):
        if compatible is not None:
            status = "PASS" if compatible else "FAIL"
        elif expected is None or actual is None:
            status = "UNKNOWN"
        else:
            status = "PASS" if expected == actual else "FAIL"
        finding = {"rule": rule, "status": status, "required": expected, "observed": actual}
        if status == "FAIL":
            finding["remediation"] = remediation_hint(rule)
        findings.append(finding)

    check("architecture", artifact["architecture"], machine["architecture"])
    required, available = artifact.get("required_extensions"), machine.get("isa_extensions")
    check("isa_extensions", required, available, set(required or []) <= set(available or []))
    check("abi", artifact.get("abi"), machine.get("abi"))
    for name, version in artifact.get("libraries", {}).items():
        check(f"library.{name}", version, machine.get("libraries", {}).get(name))
    failed = any(f["status"] == "FAIL" for f in findings)
    decision = "FAIL" if failed else "UNKNOWN" if any(f["status"] == "UNKNOWN" for f in findings) else "REVIEW"
    return {"schema_version": 1, "decision": decision, "machine_revision": digest(machine), "artifact_revision": digest(artifact), "findings": findings,
            "physical_hardware_verified": False, "execution_verified": False, "approval_required": True,
            "scope": "Static metadata checks only. Runtime compatibility requires scoped experimental evidence.",
            "evidence": [{"claim_id": digest([machine, artifact]), "status": "REFUTED" if failed else "UNKNOWN", "assumptions": ["architecture", "isa_extensions", "abi", "libraries"], "dependencies_complete": False}]}


def plan(tests, budget):
    if not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget < 0:
        raise ValueError("budget must be a finite nonnegative number")
    ids = set()
    for test in tests:
        if not isinstance(test.get("id"), str) or test["id"] in ids:
            raise ValueError("tests require unique string IDs")
        ids.add(test["id"])
        for field in ("cost_minutes", "information_gain", "severity", "relevance"):
            v = test.get(field)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f"{field} must be finite and nonnegative")
    mandatory = [t for t in tests if t.get("mandatory")]
    used = sum(t["cost_minutes"] for t in mandatory)
    if used > budget:
        return {"status": "BLOCKED", "reason": "Mandatory coverage exceeds budget", "selected": [], "cost_minutes": 0}
    selected = list(mandatory)
    ranked = sorted((t for t in tests if not t.get("mandatory")), key=lambda t: (-t["information_gain"] * t["severity"] * t["relevance"] / (t["cost_minutes"] + 1e-9), t["id"]))
    for test in ranked:
        if used + test["cost_minutes"] <= budget:
            selected.append(test)
            used += test["cost_minutes"]
    return {"status": "PROPOSED", "selected": selected, "cost_minutes": used, "budget_minutes": budget, "approval_required": True}
