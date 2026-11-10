"""Minimal, read-only local dashboard over the SQLite report store (stdlib http.server only)."""
import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from . import store as store_module


def _handler_factory(db_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # keep the dev server quiet; failures still surface via status codes

        def _send_json(self, code, payload):
            body = json.dumps(payload, indent=2).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, code, body_text):
            body = body_text.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/reports") and self.command == "GET":
                qs = parse_qs(parsed.query)
                reports = store_module.list_reports(
                    db_path,
                    machine_revision=qs.get("machine_revision", [None])[0],
                    artifact_revision=qs.get("artifact_revision", [None])[0],
                )
                if parsed.path == "/reports":
                    self._send_json(200, {"reports": reports})
                    return
                rows = "".join(
                    f"<tr><td><a href=\"/reports/{html.escape(r['sha256'])}\">{html.escape(r['sha256'])}</a></td>"
                    f"<td>{html.escape(str(r['decision']))}</td><td>{html.escape(r['created_at'])}</td></tr>"
                    for r in reports
                )
                self._send_html(200, (
                    "<html><head><title>Kernelridge reports</title></head><body>"
                    "<h1>Kernelridge reports</h1>"
                    "<table border=\"1\"><tr><th>sha256</th><th>decision</th><th>created_at</th></tr>"
                    f"{rows}</table></body></html>"
                ))
                return
            if parsed.path.startswith("/reports/"):
                sha = parsed.path[len("/reports/"):]
                try:
                    record = store_module.show(sha, db_path)
                except ValueError:
                    self._send_json(404, {"error": f"no stored report for sha256 {sha}"})
                    return
                self._send_json(200, record)
                return
            self._send_json(404, {"error": "not found"})

    return Handler


def serve(db_path=store_module.DEFAULT_PATH, port=0, bind="127.0.0.1"):
    """Build and bind an HTTPServer without blocking; caller controls its lifecycle."""
    return HTTPServer((bind, port), _handler_factory(db_path))


def run_forever(db_path=store_module.DEFAULT_PATH, port=0, bind="127.0.0.1"):
    server = serve(db_path, port, bind)
    try:
        server.serve_forever()
    finally:
        server.server_close()
