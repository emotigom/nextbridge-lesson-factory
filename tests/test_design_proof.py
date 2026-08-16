import copy
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/lessonctl'))

from core import load_jsonish
from design_proof import validate_design_proof, verify_path
import lessonctl

PROOF=ROOT/'courses/feed-why/design/cleanroom-v1/design-proof.json'


class TestDesignProof(unittest.TestCase):
    def setUp(self):
        self.proof=load_jsonish(PROOF)

    def test_feed_why_cleanroom_proof_passes(self):
        report=verify_path(PROOF,'feed-why')
        self.assertEqual('PASS',report['status'],report)
        self.assertEqual(97,report['qualityOverall'])
        self.assertEqual(4,report['sessions'])
        self.assertIn('DESIGN_PROOF_PUBLIC_DISTRIBUTION_NOT_APPROVED',report['warnings'])
        self.assertTrue(any(x.startswith('DESIGN_PROOF_MANUAL_CHECKS_PENDING:') for x in report['warnings']))

    def test_proof_rejects_quality_total_drift(self):
        proof=copy.deepcopy(self.proof)
        proof['quality']['domains']['visualDesign']=9
        report=validate_design_proof(proof,'feed-why')
        self.assertEqual('FAIL',report['status'])
        self.assertTrue(any(x.startswith('DESIGN_PROOF_QUALITY_TOTAL_MISMATCH:') for x in report['blockers']))

    def test_proof_rejects_missing_required_artifact_role(self):
        proof=copy.deepcopy(self.proof)
        proof['artifacts']=[x for x in proof['artifacts'] if x['role']!='activity-pack']
        report=validate_design_proof(proof,'feed-why')
        self.assertIn('DESIGN_PROOF_ARTIFACT_ROLE_MISSING:activity-pack',report['blockers'])

    def test_public_qa_surfaces_cleanroom_design_proof(self):
        report=lessonctl.qa('feed-why','fast')
        self.assertEqual('PASS',report['status'],report)
        design=report['designProof']
        self.assertIsNotNone(design)
        self.assertEqual('PASS',design['status'])
        self.assertEqual('cleanroom-v1',design['designVersion'])


if __name__=='__main__': unittest.main()
