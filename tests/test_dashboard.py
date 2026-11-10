import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from kernelridge import dashboard, store
from kernelridge.core import preflight

ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmpdir.name) / 'store.db')
        machine = json.loads((ROOT / 'examples/target.json').read_text())
        artifact = json.loads((ROOT / 'examples/compatible-release.json').read_text())
        self.report = preflight(machine, artifact)
        self.saved = store.save(self.report, self.db)
        self.server = dashboard.serve(self.db, port=0, bind='127.0.0.1')
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.tmpdir.cleanup()

    def _get(self, path):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}{path}', timeout=5) as response:
            return response.status, response.read()

    def test_index_lists_reports_as_html(self):
        status, body = self._get('/')
        self.assertEqual(status, 200)
        self.assertIn(self.saved['sha256'].encode(), body)

    def test_reports_json_listing(self):
        status, body = self._get('/reports')
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(len(payload['reports']), 1)
        self.assertEqual(payload['reports'][0]['sha256'], self.saved['sha256'])

    def test_report_detail_by_sha256(self):
        status, body = self._get(f"/reports/{self.saved['sha256']}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), self.report)

    def test_unknown_report_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get('/reports/' + '0' * 64)
        self.assertEqual(ctx.exception.code, 404)
        ctx.exception.close()


if __name__ == '__main__':
    unittest.main()
