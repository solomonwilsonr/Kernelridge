import copy
import json
import unittest
from pathlib import Path
from kernelridge.core import preflight, invalidate, plan, digest

ROOT = Path(__file__).resolve().parents[1]

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.machine = json.loads((ROOT / 'examples/target.json').read_text())
        self.artifact = json.loads((ROOT / 'examples/compatible-release.json').read_text())

    def test_matching_metadata_is_not_runtime_pass(self):
        report = preflight(self.machine, self.artifact)
        self.assertEqual(report['decision'], 'REVIEW')
        self.assertFalse(report['physical_hardware_verified'])

    def test_three_incompatibility_classes(self):
        for field, value in [('architecture', 'arm64'), ('required_extensions', ['v']), ('abi', 'lp64')]:
            with self.subTest(field=field):
                artifact = dict(self.artifact, **{field: value})
                self.assertEqual(preflight(self.machine, artifact)['decision'], 'FAIL')

    def test_missing_inventory_is_unknown(self):
        del self.machine['abi']
        self.assertEqual(preflight(self.machine, self.artifact)['decision'], 'UNKNOWN')

    def test_omitted_required_extensions_is_reviewed_not_unknown(self):
        artifact = dict(self.artifact)
        artifact.pop('required_extensions', None)
        report = preflight(self.machine, artifact)
        isa_finding = next(f for f in report['findings'] if f['rule'] == 'isa_extensions')
        self.assertEqual(isa_finding['status'], 'PASS')
        self.assertEqual(report['decision'], 'REVIEW')

    def test_invalidation_and_reuse(self):
        after = copy.deepcopy(self.machine)
        after['kernel'] = '6.12'
        records = [dict(status='SUPPORTED', assumptions=['kernel'], dependencies_complete=True),
                   dict(status='SUPPORTED', assumptions=['abi'], dependencies_complete=True),
                   dict(status='SUPPORTED', assumptions=['abi'])]
        states = [r['status'] for r in invalidate(records, self.machine, after)['evidence']]
        self.assertEqual(states, ['POTENTIALLY_INVALIDATED', 'SUPPORTED', 'POTENTIALLY_INVALIDATED'])

    def test_transitive_depends_on_invalidation(self):
        after = copy.deepcopy(self.machine)
        after['kernel'] = '6.12'
        records = [
            dict(claim_id='root', status='SUPPORTED', assumptions=['kernel'], dependencies_complete=True),
            dict(claim_id='mid', status='SUPPORTED', assumptions=['abi'], dependencies_complete=True, depends_on=['root']),
            dict(claim_id='leaf', status='SUPPORTED', assumptions=['abi'], dependencies_complete=True, depends_on=['mid']),
            dict(claim_id='unrelated', status='SUPPORTED', assumptions=['abi'], dependencies_complete=True),
        ]
        states = {r['claim_id']: r['status'] for r in invalidate(records, self.machine, after)['evidence']}
        self.assertEqual(states['root'], 'POTENTIALLY_INVALIDATED')
        self.assertEqual(states['mid'], 'POTENTIALLY_INVALIDATED')
        self.assertEqual(states['leaf'], 'POTENTIALLY_INVALIDATED')
        self.assertEqual(states['unrelated'], 'SUPPORTED')

    def test_depends_on_absent_matches_prior_behavior(self):
        after = copy.deepcopy(self.machine)
        after['kernel'] = '6.12'
        records = [dict(status='SUPPORTED', assumptions=['kernel'], dependencies_complete=True),
                   dict(status='SUPPORTED', assumptions=['abi'], dependencies_complete=True),
                   dict(status='SUPPORTED', assumptions=['abi'])]
        states = [r['status'] for r in invalidate(records, self.machine, after)['evidence']]
        self.assertEqual(states, ['POTENTIALLY_INVALIDATED', 'SUPPORTED', 'POTENTIALLY_INVALIDATED'])

    def test_parent_dependencies(self):
        records = [dict(status='SUPPORTED', assumptions=['libraries'], dependencies_complete=True)]
        after = copy.deepcopy(self.machine)
        after['libraries']['glibc'] = '2.39'
        self.assertEqual(invalidate(records, self.machine, after)['evidence'][0]['status'], 'POTENTIALLY_INVALIDATED')

    def test_mandatory_coverage_cannot_be_dropped(self):
        tests = json.loads((ROOT / 'examples/catalog.json').read_text())
        self.assertEqual(plan(tests, 1)['status'], 'BLOCKED')
        result = plan(tests, 7)
        self.assertEqual(result['cost_minutes'], 7)
        self.assertEqual(result['selected'][0]['id'], 'smoke')
        with self.assertRaises(ValueError):
            plan(tests, float('nan'))

    def test_hash_is_canonical(self):
        self.assertEqual(digest({'a': 1, 'b': 2}), digest({'b': 2, 'a': 1}))

if __name__ == '__main__':
    unittest.main()
