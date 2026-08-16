import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF_FIXTURE = ROOT / 'fixtures' / 'handoff' / 'chatgpt-pass' / 'handoff.json'

spec = importlib.util.spec_from_file_location('handoff', ROOT / 'tools' / 'lessonctl' / 'handoff.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class TestChatGPTHandoff(unittest.TestCase):
    def setUp(self):
        self.handoff = json.loads(HANDOFF_FIXTURE.read_text(encoding='utf-8'))

    def test_complete_handoff_passes(self):
        report = h.validate_handoff(self.handoff)
        self.assertEqual('PASS', report['status'], report)
        self.assertEqual('ALL_CONTENT_APPROVED', report['designState'])
        self.assertEqual([1], report['approvedSessions'])

    def test_materialize_produces_existing_factory_bundle_contract(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'bundle'
            report = h.materialize_handoff(self.handoff, out)
            self.assertEqual('PASS', report['status'], report)
            self.assertEqual('PASS', report['contentDesign']['status'], report)
            self.assertTrue((out / 'source-policy.json').is_file())
            self.assertTrue((out / 'storyboards' / 'session-1.json').is_file())

    def test_partial_handoff_can_validate_but_cannot_materialize(self):
        partial = copy.deepcopy(self.handoff)
        partial['designState'] = 'COURSE_MAP_APPROVED'
        partial['storyboards'] = []
        partial['qualityScore'] = None
        partial['approvals']['sessions'][0] = {'session':1,'status':'PENDING','reviewer':None,'approvedAt':None}
        partial['approvals']['allContent'] = {'status':'PENDING','reviewer':None,'approvedAt':None}
        report = h.validate_handoff(partial)
        self.assertEqual('PASS', report['status'], report)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(Exception):
                h.materialize_handoff(partial, Path(td) / 'bundle')

    def test_approval_gap_or_storyboard_drift_is_rejected(self):
        bad = copy.deepcopy(self.handoff)
        bad['approvals']['sessions'][0]['status'] = 'PENDING'
        bad['approvals']['sessions'][0]['reviewer'] = None
        bad['approvals']['sessions'][0]['approvedAt'] = None
        report = h.validate_handoff(bad)
        self.assertEqual('FAIL', report['status'])
        self.assertIn('STORYBOARD_SET_DOES_NOT_MATCH_APPROVED_SESSIONS', report['blockers'])

    def test_design_state_is_derived_not_trusted(self):
        bad = copy.deepcopy(self.handoff)
        bad['designState'] = 'COURSE_MAP_APPROVED'
        report = h.validate_handoff(bad)
        self.assertIn('DESIGN_STATE_MISMATCH:COURSE_MAP_APPROVED!=ALL_CONTENT_APPROVED', report['blockers'])

    def test_all_content_requires_quality_score(self):
        bad = copy.deepcopy(self.handoff)
        bad['qualityScore'] = None
        report = h.validate_handoff(bad)
        self.assertIn('ALL_CONTENT_REQUIRES_QUALITY_SCORE', report['blockers'])

    def test_conversation_detail_cannot_be_marked_public(self):
        bad = copy.deepcopy(self.handoff)
        bad['privateConversationEvidence']['detailPublished'] = True
        report = h.validate_handoff(bad)
        self.assertEqual('FAIL', report['status'])

    def test_schema_is_valid_json(self):
        json.loads((ROOT / 'contracts' / 'chatgpt-handoff.schema.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
