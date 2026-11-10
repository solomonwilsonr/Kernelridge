import json
import tempfile
import unittest
from pathlib import Path
from kernelridge import mcp_server
from kernelridge.core import digest

ROOT = Path(__file__).resolve().parents[1]


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.machine = json.loads((ROOT / 'examples/target.json').read_text())
        self.artifact = json.loads((ROOT / 'examples/compatible-release.json').read_text())

    def test_initialize(self):
        response = mcp_server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["result"]["protocolVersion"], mcp_server.PROTOCOL_VERSION)
        self.assertEqual(response["result"]["serverInfo"]["name"], "kernelridge")

    def test_initialized_notification_is_silent(self):
        self.assertIsNone(mcp_server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}))

    def test_tools_list_matches_registry(self):
        response = mcp_server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in response["result"]["tools"]}
        self.assertEqual(names, set(mcp_server.TOOLS.keys()))
        for tool in response["result"]["tools"]:
            self.assertIn("description", tool)
            self.assertIn("inputSchema", tool)

    def test_preflight_tool_call_matches_direct_call(self):
        from kernelridge.core import preflight
        direct = preflight(self.machine, self.artifact)
        response = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "preflight", "arguments": {"machine": self.machine, "artifact": self.artifact}},
        })
        self.assertFalse(response["result"]["isError"])
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(payload, direct)

    def test_unknown_tool_is_reported_as_tool_error_not_protocol_error(self):
        response = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "does_not_exist", "arguments": {}},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("unknown tool", response["result"]["content"][0]["text"])

    def test_missing_required_argument_is_tool_error(self):
        response = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "preflight", "arguments": {"machine": self.machine}},
        })
        self.assertTrue(response["result"]["isError"])

    def test_unexpected_handler_exception_is_tool_error_not_a_crash(self):
        response = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 9, "method": "tools/call",
            "params": {"name": "store_show", "arguments": {"sha256": "x" * 64, "db": "/nonexistent/dir/store.db"}},
        })
        self.assertTrue(response["result"]["isError"])

    def test_unknown_method_is_protocol_error(self):
        response = mcp_server.handle_request({"jsonrpc": "2.0", "id": 6, "method": "bogus/method"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_store_round_trip_via_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / 'store.db')
            from kernelridge.core import preflight
            report = preflight(self.machine, self.artifact)
            save_response = mcp_server.handle_request({
                "jsonrpc": "2.0", "id": 7, "method": "tools/call",
                "params": {"name": "store_save", "arguments": {"record": report, "db": db}},
            })
            saved = json.loads(save_response["result"]["content"][0]["text"])
            self.assertEqual(saved["sha256"], digest(report))
            show_response = mcp_server.handle_request({
                "jsonrpc": "2.0", "id": 8, "method": "tools/call",
                "params": {"name": "store_show", "arguments": {"sha256": saved["sha256"], "db": db}},
            })
            fetched = json.loads(show_response["result"]["content"][0]["text"])
            self.assertEqual(fetched, report)

    def test_serve_loop_over_in_memory_streams(self):
        import io
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        stdin = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
        stdout = io.StringIO()
        mcp_server.serve(stdin=stdin, stdout=stdout)
        lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        responses = [json.loads(line) for line in lines]
        self.assertEqual([r["id"] for r in responses], [1, 2])


if __name__ == '__main__':
    unittest.main()
