#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core import ROOT, check_schema_subset, load_jsonish

SCHEMAS = {
    'source': ROOT / 'contracts' / 'clean-room-source.schema.json',
    'map': ROOT / 'contracts' / 'course-map.schema.json',
    'storyboard': ROOT / 'contracts' / 'storyboard.schema.json',
    'quality': ROOT / 'contracts' / 'quality-rubric.schema.json',
    'concept': ROOT / 'contracts' / 'concept-order.schema.json',
}
LANGUAGE_POLICY = ROOT / 'policies' / 'student-language.json'
DEFAULT_CONCEPT_POLICY = ROOT / 'policies' / 'concept-order.json'
QUALITY_POLICY = ROOT / 'policies' / 'quality-rubric.json'
ACTION_ROLES = {'THINK', 'CHOOSE', 'TRY', 'TALK', 'CHECK'}


def _schema_errors(data, key):
    return check_schema_subset(data, load_jsonish(SCHEMAS[key]))


def _report(name, blockers=None, warnings=None, detail=None):
    blockers = blockers or []
    warnings = warnings or []
    return {
        'name': name,
        'status': 'FAIL' if blockers else 'PASS',
        'blockers': blockers,
        'warnings': warnings,
        'detail': detail or {},
    }


def validate_source_policy(data):
    blockers = [f'SCHEMA:{e}' for e in _schema_errors(data, 'source')]
    ids = [x.get('id') for x in data.get('allowedInputs', []) if isinstance(x, dict)]
    if len(ids) != len(set(ids)):
        blockers.append('DUPLICATE_ALLOWED_INPUT_ID')
    if data.get('priorArtifactPolicy') != 'deny-unless-explicitly-approved':
        blockers.append('PRIOR_ARTIFACT_POLICY_NOT_CLEAN_ROOM')
    copy = data.get('copyPolicy', {})
    if any(copy.get(k) is not False for k in ('copyPriorWording', 'copyPriorLayout', 'copyPriorActivities', 'copyPriorVisualSystem')):
        blockers.append('PRIOR_ARTIFACT_COPY_NOT_DENIED')
    return _report('clean_room_source', blockers)


def validate_course_map(data):
    blockers = [f'SCHEMA:{e}' for e in _schema_errors(data, 'map')]
    sessions = data.get('sessions', [])
    numbers = [x.get('session') for x in sessions if isinstance(x, dict)]
    if numbers != list(range(1, len(numbers) + 1)):
        blockers.append('SESSION_NUMBERS_NOT_CONTIGUOUS')
    if not data.get('locked'):
        blockers.append('COURSE_MAP_NOT_LOCKED')
    if any(x.get('status') != 'APPROVED' for x in sessions if isinstance(x, dict)):
        blockers.append('COURSE_MAP_SESSION_NOT_APPROVED')
    return _report('course_map', blockers, detail={'sessions': len(sessions)})


def validate_concept_policy(data):
    blockers = [f'SCHEMA:{e}' for e in _schema_errors(data, 'concept')]
    ids = []
    labels = []
    for term in data.get('terms', []):
        if not isinstance(term, dict):
            continue
        ids.append(term.get('id'))
        labels.extend(term.get('labels', []))
    if len(ids) != len(set(ids)):
        blockers.append('DUPLICATE_CONCEPT_ID')
    if len(labels) != len(set(labels)):
        blockers.append('DUPLICATE_CONCEPT_LABEL')
    return _report('concept_policy', blockers, detail={'protectedTerms': len(ids)})


def _concept_index(policy):
    index = {}
    for term in policy.get('terms', []):
        term_id = term['id']
        for label in term.get('labels', []):
            index[label] = term_id
    return index


def _normalized_introductions(values, concept_index):
    ids = set()
    valid_ids = set(concept_index.values())
    for value in values or []:
        if value in valid_ids:
            ids.add(value)
        elif value in concept_index:
            ids.add(concept_index[value])
    return ids


def validate_storyboard(data, concept_policy=None):
    blockers = [f'SCHEMA:{e}' for e in _schema_errors(data, 'storyboard')]
    warnings = []
    language = load_jsonish(LANGUAGE_POLICY)
    concept_policy = concept_policy or load_jsonish(DEFAULT_CONCEPT_POLICY)
    concept_index = _concept_index(concept_policy)
    slides = data.get('slides', [])
    beats = data.get('teachingBeats', [])
    beat_ids = {x.get('beat') for x in beats if isinstance(x, dict)}

    slide_numbers = [x.get('slide') for x in slides if isinstance(x, dict)]
    if slide_numbers != list(range(1, len(slide_numbers) + 1)):
        blockers.append('SLIDE_NUMBERS_NOT_CONTIGUOUS')
    if any(x.get('teachingBeat') not in beat_ids for x in slides if isinstance(x, dict)):
        blockers.append('UNKNOWN_TEACHING_BEAT')
    if data.get('status') != 'APPROVED':
        blockers.append('STORYBOARD_NOT_APPROVED')

    core_minutes = sum(float(x.get('minutes', 0) or 0) for x in slides if x.get('priority') == 'CORE')
    full_minutes = sum(float(x.get('minutes', 0) or 0) for x in slides)
    timing = data.get('timing', {})
    tolerance = float(timing.get('coreToleranceMinutes', 0) or 0)
    if abs(core_minutes - float(timing.get('coreTargetMinutes', 0) or 0)) > tolerance:
        blockers.append('CORE_TIME_OUTSIDE_TOLERANCE')
    if abs(full_minutes - float(timing.get('fullTargetMinutes', 0) or 0)) > tolerance:
        blockers.append('FULL_TIME_OUTSIDE_TOLERANCE')

    elapsed = 0.0
    first_action_at = None
    introduced = set()
    consecutive_learn = 0
    max_consecutive_learn = 0
    forbidden_hits = []
    warning_hits = []
    concept_early_hits = []

    for slide in slides:
        role = slide.get('role')
        priority = slide.get('priority')
        if priority == 'BUFFER':
            if slide.get('skippable') is not True:
                blockers.append(f'BUFFER_NOT_SKIPPABLE:S{slide.get("slide")}')
            if slide.get('conceptsIntroduced'):
                blockers.append(f'BUFFER_INTRODUCES_REQUIRED_CONCEPT:S{slide.get("slide")}')

        if first_action_at is None and role in ACTION_ROLES:
            first_action_at = elapsed
        elapsed += float(slide.get('minutes', 0) or 0)

        text = slide.get('studentText', '') or ''
        for phrase in language.get('forbiddenPhrases', []):
            if phrase and phrase in text:
                forbidden_hits.append((slide.get('slide'), phrase))
        for phrase in language.get('warningPhrases', []):
            if phrase and phrase in text:
                warning_hits.append((slide.get('slide'), phrase))
        max_chars = int(language.get('heuristics', {}).get('maxCharactersPerStudentText', 0) or 0)
        if max_chars and len(text) > max_chars:
            warnings.append(f'STUDENT_TEXT_LONG:S{slide.get("slide")}:{len(text)}')

        current_intro = _normalized_introductions(slide.get('conceptsIntroduced', []), concept_index)
        if concept_policy.get('introduceAfterExperience'):
            for label, term_id in concept_index.items():
                if label in text and term_id not in introduced and term_id not in current_intro:
                    concept_early_hits.append((slide.get('slide'), label))
        introduced.update(current_intro)

        if role == 'LEARN':
            consecutive_learn += 1
            max_consecutive_learn = max(max_consecutive_learn, consecutive_learn)
        else:
            consecutive_learn = 0

    if first_action_at is None or first_action_at >= 3.0:
        blockers.append('FIRST_STUDENT_ACTION_NOT_WITHIN_3_MINUTES')
    if forbidden_hits:
        blockers.extend(f'STUDENT_LANGUAGE_FORBIDDEN:S{s}:{p}' for s, p in forbidden_hits)
    if concept_early_hits:
        blockers.extend(f'CONCEPT_BEFORE_INTRO:S{s}:{p}' for s, p in concept_early_hits)
    if warning_hits:
        warnings.extend(f'STUDENT_LANGUAGE_WARNING:S{s}:{p}' for s, p in warning_hits)
    if max_consecutive_learn >= 3:
        blockers.append('LEARN_RUN_TOO_LONG')
    elif max_consecutive_learn == 2:
        warnings.append('CONSECUTIVE_LEARN_SLIDES')
    if not 6 <= len(beats) <= 8:
        warnings.append(f'TEACHING_BEAT_COUNT_OUTSIDE_TARGET:{len(beats)}')
    if not 18 <= len(slides) <= 22:
        warnings.append(f'SLIDE_COUNT_OUTSIDE_TARGET:{len(slides)}')

    return _report(
        'storyboard',
        blockers,
        warnings,
        {
            'session': data.get('session'),
            'slides': len(slides),
            'teachingBeats': len(beats),
            'coreMinutes': core_minutes,
            'fullMinutes': full_minutes,
            'firstActionAtMinute': first_action_at,
        },
    )


def validate_quality_score(data):
    blockers = [f'SCHEMA:{e}' for e in _schema_errors(data, 'quality')]
    rubric = load_jsonish(QUALITY_POLICY)
    expected = [x['id'] for x in rubric.get('criteria', [])]
    scores = data.get('criteria', {})
    if set(scores) != set(expected):
        blockers.append('QUALITY_CRITERIA_SET_MISMATCH')
    calculated = sum(scores.get(cid, 0) for cid in expected)
    if data.get('overall') != calculated:
        blockers.append(f'QUALITY_OVERALL_MISMATCH:{data.get("overall")}!={calculated}')
    minimum = int(rubric.get('hardGateMinimum', 3))
    hard_ids = [x['id'] for x in rubric.get('criteria', []) if x.get('hardGate')]
    hard_pass = all(scores.get(cid, -1) >= minimum for cid in hard_ids)
    if data.get('hardGatesPass') is not hard_pass:
        blockers.append('QUALITY_HARD_GATE_FLAG_MISMATCH')
    if not hard_pass:
        blockers.append('QUALITY_HARD_GATE_BELOW_MINIMUM')
    return _report('quality_score', blockers, detail={'overall': calculated, 'hardGateIds': hard_ids})


def check_bundle(bundle_dir: Path):
    bundle_dir = bundle_dir.resolve()
    reports = []
    source_path = bundle_dir / 'source-policy.json'
    map_path = bundle_dir / 'course-map.json'
    concept_path = bundle_dir / 'concept-policy.json'
    storyboard_dir = bundle_dir / 'storyboards'
    quality_path = bundle_dir / 'quality-score.json'

    required_files = (source_path, map_path, concept_path, quality_path)
    for required in required_files:
        if not required.is_file():
            reports.append(_report(required.name, [f'MISSING_REQUIRED_FILE:{required.name}']))
    if not storyboard_dir.is_dir():
        reports.append(_report('storyboards', ['MISSING_REQUIRED_DIR:storyboards']))
    if reports:
        blockers = [b for report in reports for b in report.get('blockers', [])]
        return {'schemaVersion': '1.0.0', 'status': 'FAIL', 'bundle': str(bundle_dir), 'reports': reports, 'blockers': blockers, 'warnings': []}

    source = load_jsonish(source_path)
    course_map = load_jsonish(map_path)
    concept_policy = load_jsonish(concept_path)
    quality = load_jsonish(quality_path)
    reports.extend([
        validate_source_policy(source),
        validate_course_map(course_map),
        validate_concept_policy(concept_policy),
        validate_quality_score(quality),
    ])

    course_id = course_map.get('courseId')
    if quality.get('courseId') != course_id:
        reports.append(_report('course_id_consistency', ['QUALITY_COURSE_ID_MISMATCH']))

    map_sessions = [x.get('session') for x in course_map.get('sessions', [])]
    storyboards = [(p, load_jsonish(p)) for p in storyboard_dir.glob('session-*.json')]
    storyboards.sort(key=lambda item: (item[1].get('session', 10**9), item[0].name))
    storyboard_sessions = [x.get('session') for _, x in storyboards]
    if storyboard_sessions != map_sessions:
        reports.append(_report('storyboard_inventory', ['STORYBOARD_SESSION_SET_MISMATCH'], detail={'map': map_sessions, 'storyboards': storyboard_sessions}))
    for path, storyboard in storyboards:
        if storyboard.get('courseId') != course_id:
            reports.append(_report('course_id_consistency', [f'STORYBOARD_COURSE_ID_MISMATCH:{path.name}']))
        rep = validate_storyboard(storyboard, concept_policy)
        rep['path'] = str(path.relative_to(bundle_dir))
        reports.append(rep)

    blockers = [b for report in reports for b in report.get('blockers', [])]
    warnings = [w for report in reports for w in report.get('warnings', [])]
    return {
        'schemaVersion': '1.0.0',
        'status': 'FAIL' if blockers else 'PASS',
        'bundle': str(bundle_dir),
        'reports': reports,
        'blockers': blockers,
        'warnings': warnings,
    }


def main():
    parser = argparse.ArgumentParser(prog='content_design')
    sub = parser.add_subparsers(dest='cmd', required=True)
    check = sub.add_parser('check')
    check.add_argument('--path', required=True)
    check.add_argument('--json', dest='jsonout')
    args = parser.parse_args()

    if args.cmd == 'check':
        report = check_bundle(Path(args.path))
        text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.jsonout:
            out = Path(args.jsonout)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding='utf-8')
        print(text, end='')
        raise SystemExit(0 if report['status'] == 'PASS' else 2)


if __name__ == '__main__':
    main()
