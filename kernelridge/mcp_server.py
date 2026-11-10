"""Minimal MCP (Model Context Protocol) server over stdio.

Hand-rolled JSON-RPC 2.0 framing per the MCP stdio transport (one JSON object
per line on stdin/stdout) -- no third-party MCP SDK dependency. Exposes the
same deterministic operations as the CLI as MCP tools so an MCP client can
call preflight/inspect/invalidate/experiment-plan/report/store directly.
"""
import json
import sys

from .core import digest, invalidate, plan, preflight
from .elf import inspect as elf_inspect
from . import store as store_module

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "kernelridge"
SERVER_VERSION = "0.1.0"


def _tool_preflight(arguments):
    return preflight(arguments["machine"], arguments["artifact"])


def _tool_invalidate(arguments):
    return invalidate(arguments["evidence"], arguments["before"], arguments["after"])


def _tool_experiment_plan(arguments):
    return plan(arguments["catalog"], arguments["budget_minutes"])


def _tool_inspect(arguments):
    return elf_inspect(arguments["binary_path"])


def _tool_report(arguments):
    record = arguments["record"]
    return {"report": record, "sha256": digest(record), "signed": False, "approval_required": True}


def _tool_store_save(arguments):
    return store_module.save(arguments["record"], arguments.get("db", store_module.DEFAULT_PATH))


def _tool_store_list(arguments):
    reports = store_module.list_reports(
        arguments.get("db", store_module.DEFAULT_PATH),
        arguments.get("machine_revision"),
        arguments.get("artifact_revision"),
    )
    return {"reports": reports}


def _tool_store_show(arguments):
    return store_module.show(arguments["sha256"], arguments.get("db", store_module.DEFAULT_PATH))


TOOLS = {
    "preflight": {
        "description": "Check a release artifact against a target machine's architecture, ISA extensions, ABI, and library versions. Never returns an optimistic PASS: a static match is REVIEW, a mismatch is FAIL, missing data is UNKNOWN.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "machine": {"type": "object", "description": "Target machine manifest (id, architecture, isa_extensions, abi, libraries)"},
                "artifact": {"type": "object", "description": "Release artifact manifest (id, architecture, required_extensions, abi, libraries)"},
            },
            "required": ["machine", "artifact"],
        },
        "handler": _tool_preflight,
    },
    "invalidate": {
        "description": "Compare a before/after revision pair and flag evidence records affected by the change, propagating transitively over an explicit depends_on graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "before": {"type": "object"},
                "after": {"type": "object"},
                "evidence": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["before", "after", "evidence"],
        },
        "handler": _tool_invalidate,
    },
    "experiment_plan": {
        "description": "Reserve mandatory experiment coverage within a time budget, then rank optional experiments by information gain x severity x relevance / cost.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "catalog": {"type": "array", "items": {"type": "object"}},
                "budget_minutes": {"type": "number"},
            },
            "required": ["catalog", "budget_minutes"],
        },
        "handler": _tool_experiment_plan,
    },
    "inspect": {
        "description": "Derive a machine/artifact-shaped JSON fragment (architecture, ABI, ISA extensions) from a real ELF binary's header, for feeding into preflight.",
        "inputSchema": {
            "type": "object",
            "properties": {"binary_path": {"type": "string"}},
            "required": ["binary_path"],
        },
        "handler": _tool_inspect,
    },
    "report": {
        "description": "Wrap a JSON record with its canonical SHA-256 digest. Unsigned; not a cryptographic attestation.",
        "inputSchema": {
            "type": "object",
            "properties": {"record": {"type": "object"}},
            "required": ["record"],
        },
        "handler": _tool_report,
    },
    "store_save": {
        "description": "Persist a preflight/attest report in a local SQLite store keyed by its canonical digest.",
        "inputSchema": {
            "type": "object",
            "properties": {"record": {"type": "object"}, "db": {"type": "string"}},
            "required": ["record"],
        },
        "handler": _tool_store_save,
    },
    "store_list": {
        "description": "List stored report history, optionally filtered by machine_revision/artifact_revision.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db": {"type": "string"},
                "machine_revision": {"type": "string"},
                "artifact_revision": {"type": "string"},
            },
        },
        "handler": _tool_store_list,
    },
    "store_show": {
        "description": "Fetch a single stored report by its SHA-256 digest.",
        "inputSchema": {
            "type": "object",
            "properties": {"sha256": {"type": "string"}, "db": {"type": "string"}},
            "required": ["sha256"],
        },
        "handler": _tool_store_show,
    },
}


def _tools_list_payload():
    return {"tools": [{"name": name, "description": tool["description"], "inputSchema": tool["inputSchema"]} for name, tool in TOOLS.items()]}


def _call_tool(name, arguments):
    tool = TOOLS.get(name)
    if tool is None:
        raise ValueError(f"unknown tool: {name}")
    return tool["handler"](arguments or {})


def handle_request(message):
    """Return a JSON-RPC response dict, or None for a notification (no id)."""
    msg_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}
    is_notification = "id" not in message

    def ok(result):
        return None if is_notification else {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def err(code, text):
        return None if is_notification else {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": text}}

    if method == "initialize":
        return ok({
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok(_tools_list_payload())
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments")
        try:
            result = _call_tool(name, arguments)
        except Exception as exc:  # a single bad tool call must not kill the stdio server loop
            return ok({"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True})
        return ok({"content": [{"type": "text", "text": json.dumps(result, allow_nan=False)}], "isError": False})
    return err(-32601, f"method not found: {method}")


def serve(stdin=None, stdout=None):
    """Run the stdio JSON-RPC loop until stdin closes. One JSON message per line."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "invalid JSON"}}
        else:
            response = handle_request(message)
        if response is not None:
            stdout.write(json.dumps(response, allow_nan=False) + "\n")
            stdout.flush()
