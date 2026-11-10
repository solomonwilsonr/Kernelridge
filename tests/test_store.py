import json
import tempfile
import unittest
from pathlib import Path
from kernelridge import store
from kernelridge.core import preflight, digest

ROOT = Path(__file__).resolve().parents[1]


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.machine = json.loads((ROOT / 'examples/target.json').read_text())
        self.artifact = json.loads((ROOT / 'examples/compatible-release.json').read_text())
        self.report = preflight(self.machine, self.artifact)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmpdir.name) / 'nested' / 'store.db')

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_and_show_round_trip(self):
        saved = store.save(self.report, self.db)
        self.assertEqual(saved['sha256'], digest(self.report))
        self.assertTrue(Path(self.db).exists())
        fetched = store.show(saved['sha256'], self.db)
        self.assertEqual(fetched, self.report)

    def test_list_filters_by_revision(self):
        store.save(self.report, self.db)
        other = dict(self.report, machine_revision='different')
        store.save(other, self.db)
        all_rows = store.list_reports(self.db)
        self.assertEqual(len(all_rows), 2)
        filtered = store.list_reports(self.db, machine_revision=self.report['machine_revision'])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['sha256'], digest(self.report))

    def test_show_missing_raises(self):
        store.save(self.report, self.db)
        with self.assertRaises(ValueError):
            store.show('0' * 64, self.db)

    def test_save_is_idempotent(self):
        first = store.save(self.report, self.db)
        second = store.save(self.report, self.db)
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual(len(store.list_reports(self.db)), 1)


if __name__ == '__main__':
    unittest.main()
