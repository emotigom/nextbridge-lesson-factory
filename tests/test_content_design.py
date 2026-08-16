import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'lessonctl'))

from content_design import (
    check_bundle,
    validate_concept_policy,
    validate_course_map,
    validate_quality_score,
    validate_source_policy,
    validate_storyboard,
)
from core import load_jsonish


FIXTURE = ROOT / 'fixtures' / 'design' / 'clean-room-pass'


class TestContentDesign(unittest.TestCase):
    def setUp(self):
        self.source = load_jsonish(FIXTURE / 'source-policy.json')
        self.course_map = load_jsonish(FIXTURE / 'course-map.json')
        self.concepts = load_jsonish(FIXTURE / 'concept-policy.json')
        self.storyboard = load_jsonish(FIXTURE / 'storyboards' / 'session-1.json')
        self.quality = load_jsonish(FIXTURE / 'quality-score.json')

    def test_passing_bundle(self):
        report = check_bundle(FIXTURE)
        self.assertEqual('PASS', report['status'], report)
        self.assertEqual([], report['blockers'])

    def test_clean_room_rejects_prior_copy(self):
        source = copy.deepcopy(self.source)
        source['copyPolicy']['copyPriorWording'] = True
        report = validate_source_policy(source)
        self.assertEqual('FAIL', report['status'])
        self.assertIn('PRIOR_ARTIFACT_COPY_NOT_DENIED', report['blockers'])

    def test_course_map_requires_locked_contiguous_approved_sessions(self):
        course_map = copy.deepcopy(self.course_map)
        course_map['locked'] = False
        course_map['sessions'][0]['session'] = 2
        course_map['sessions'][0]['status'] = 'DRAFT'
        blockers = validate_course_map(course_map)['blockers']
        self.assertIn('COURSE_MAP_NOT_LOCKED', blockers)
        self.assertIn('SESSION_NUMBERS_NOT_CONTIGUOUS', blockers)
        self.assertIn('COURSE_MAP_SESSION_NOT_APPROVED', blockers)

    def test_concept_policy_rejects_duplicate_labels(self):
        concepts = copy.deepcopy(self.concepts)
        concepts['terms'].append({'id':'another','labels':['가중치']})
        self.assertIn('DUPLICATE_CONCEPT_LABEL', validate_concept_policy(concepts)['blockers'])

    def test_storyboard_rejects_ai_report_language_on_student_screen(self):
        storyboard = copy.deepcopy(self.storyboard)
        storyboard['slides'][1]['studentText'] = '본 활동은 가중치 테스트 케이스를 확인했습니다.'
        report = validate_storyboard(storyboard, self.concepts)
        self.assertEqual('FAIL', report['status'])
        self.assertTrue(any(x.startswith('STUDENT_LANGUAGE_FORBIDDEN:S2:') for x in report['blockers']))

    def test_storyboard_rejects_concept_before_experience_intro(self):
        storyboard = copy.deepcopy(self.storyboard)
        storyboard['slides'][1]['studentText'] = '가중치를 먼저 골라보세요.'
        report = validate_storyboard(storyboard, self.concepts)
        self.assertIn('CONCEPT_BEFORE_INTRO:S2:가중치', report['blockers'])

    def test_factory_default_concept_policy_is_course_neutral(self):
        storyboard = copy.deepcopy(self.storyboard)
        storyboard['slides'][1]['studentText'] = '가중치를 먼저 골라보세요.'
        report = validate_storyboard(storyboard)
        self.assertFalse(any(x.startswith('CONCEPT_BEFORE_INTRO:') for x in report['blockers']))

    def test_buffer_cannot_introduce_required_concept(self):
        storyboard = copy.deepcopy(self.storyboard)
        storyboard['slides'][-1]['conceptsIntroduced'] = ['weight']
        report = validate_storyboard(storyboard, self.concepts)
        self.assertIn('BUFFER_INTRODUCES_REQUIRED_CONCEPT:S7', report['blockers'])

    def test_storyboard_requires_first_action_within_three_minutes(self):
        storyboard = copy.deepcopy(self.storyboard)
        storyboard['slides'][0]['minutes'] = 3.5
        storyboard['slides'][5]['minutes'] = 13.0
        report = validate_storyboard(storyboard, self.concepts)
        self.assertIn('FIRST_STUDENT_ACTION_NOT_WITHIN_3_MINUTES', report['blockers'])

    def test_quality_score_recomputes_total_and_hard_gates(self):
        quality = copy.deepcopy(self.quality)
        quality['criteria']['Q05'] = 2
        quality['overall'] = 97
        quality['hardGatesPass'] = False
        report = validate_quality_score(quality)
        self.assertEqual('FAIL', report['status'])
        self.assertIn('QUALITY_HARD_GATE_BELOW_MINIMUM', report['blockers'])
        self.assertFalse(any(x.startswith('QUALITY_OVERALL_MISMATCH:') for x in report['blockers']))

    def test_schema_and_policy_json_files_are_valid_json(self):
        paths = [
            ROOT / 'contracts' / 'clean-room-source.schema.json',
            ROOT / 'contracts' / 'course-map.schema.json',
            ROOT / 'contracts' / 'concept-order.schema.json',
            ROOT / 'contracts' / 'storyboard.schema.json',
            ROOT / 'contracts' / 'quality-rubric.schema.json',
            ROOT / 'policies' / 'quality-rubric.json',
            ROOT / 'policies' / 'student-language.json',
            ROOT / 'policies' / 'concept-order.json',
            FIXTURE / 'concept-policy.json',
        ]
        for path in paths:
            with self.subTest(path=path):
                json.loads(path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
