#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from core import ROOT, QAError, check_schema_subset, load_jsonish
from content_design import (
    check_bundle,
    validate_concept_policy,
    validate_course_map,
    validate_quality_score,
    validate_source_policy,
    validate_storyboard,
)

SCHEMA = ROOT / 'contracts' / 'chatgpt-handoff.schema.json'


def _approved(record):
    return isinstance(record, dict) and record.get('status') == 'APPROVED'


def _metadata_blockers(name, record):
    blockers = []
    if not isinstance(record, dict):
        return [f'APPROVAL_RECORD_INVALID:{name}']
    if record.get('status') not in ('PENDING', 'APPROVED'):
        blockers.append(f'APPROVAL_STATUS_INVALID:{name}')
    if record.get('status') == 'APPROVED':
        if not record.get('reviewer'):
            blockers.append(f'APPROVAL_REVIEWER_MISSING:{name}')
        if not record.get('approvedAt'):
            blockers.append(f'APPROVAL_TIME_MISSING:{name}')
    return blockers


def expected_design_state(handoff):
    approvals = handoff['approvals']
    approved_count = 0
    for record in approvals['sessions']:
        if _approved(record):
            approved_count += 1
        else:
            break
    if _approved(approvals['allContent']):
        return 'ALL_CONTENT_APPROVED'
    if approved_count:
        return f'SESSION_{approved_count}_APPROVED'
    return 'COURSE_MAP_APPROVED'


def validate_handoff(handoff):
    schema = load_jsonish(SCHEMA)
    blockers = [f'SCHEMA:{e}' for e in check_schema_subset(handoff, schema)]
    warnings = []
    if blockers:
        return {'status':'FAIL','blockers':blockers,'warnings':warnings}

    cid = handoff['courseId']
    nested = [
        validate_source_policy(handoff['sourcePolicy']),
        validate_course_map(handoff['courseMap']),
        validate_concept_policy(handoff['conceptPolicy']),
    ]
    for report in nested:
        blockers.extend(f'{report["name"]}:{x}' for x in report.get('blockers', []))
        warnings.extend(f'{report["name"]}:{x}' for x in report.get('warnings', []))

    if handoff['courseMap'].get('courseId') != cid:
        blockers.append('COURSE_ID_MISMATCH:courseMap')

    sessions = handoff['courseMap'].get('sessions', [])
    session_numbers = [x.get('session') for x in sessions if isinstance(x, dict)]
    approvals = handoff['approvals']
    blockers.extend(_metadata_blockers('cleanIntake', approvals.get('cleanIntake')))
    blockers.extend(_metadata_blockers('courseMap', approvals.get('courseMap')))
    blockers.extend(_metadata_blockers('allContent', approvals.get('allContent')))
    if not _approved(approvals.get('cleanIntake')):
        blockers.append('CLEAN_INTAKE_NOT_APPROVED')
    if not _approved(approvals.get('courseMap')):
        blockers.append('COURSE_MAP_NOT_APPROVED')

    session_approvals = approvals.get('sessions', [])
    if len(session_approvals) != len(sessions):
        blockers.append('SESSION_APPROVAL_COUNT_MISMATCH')
    numbers = [x.get('session') for x in session_approvals if isinstance(x, dict)]
    if numbers != session_numbers:
        blockers.append('SESSION_APPROVAL_NUMBERS_MISMATCH')
    for i, record in enumerate(session_approvals, 1):
        blockers.extend(_metadata_blockers(f'session{i}', record))

    seen_pending = False
    approved_sessions = []
    for i, record in enumerate(session_approvals, 1):
        approved = _approved(record)
        if not approved:
            seen_pending = True
        elif seen_pending:
            blockers.append(f'SESSION_APPROVAL_GAP:SESSION_{i}')
        if approved:
            approved_sessions.append(i)

    delivery_profile = handoff['courseMap'].get('deliveryProfile')
    storyboard_sessions = []
    for storyboard in handoff.get('storyboards', []):
        storyboard_sessions.append(storyboard.get('session'))
        if storyboard.get('courseId') != cid:
            blockers.append(f'COURSE_ID_MISMATCH:storyboard:{storyboard.get("session")}')
        report = validate_storyboard(storyboard, handoff['conceptPolicy'], delivery_profile)
        blockers.extend(f'storyboard-{storyboard.get("session")}:{x}' for x in report.get('blockers', []))
        warnings.extend(f'storyboard-{storyboard.get("session")}:{x}' for x in report.get('warnings', []))
    if storyboard_sessions != approved_sessions:
        blockers.append('STORYBOARD_SET_DOES_NOT_MATCH_APPROVED_SESSIONS')

    if _approved(approvals.get('allContent')) and approved_sessions != session_numbers:
        blockers.append('ALL_CONTENT_APPROVED_BEFORE_ALL_SESSIONS')
    quality = handoff.get('qualityScore')
    if _approved(approvals.get('allContent')) and quality is None:
        blockers.append('ALL_CONTENT_REQUIRES_QUALITY_SCORE')
    if quality is not None:
        if quality.get('courseId') != cid:
            blockers.append('COURSE_ID_MISMATCH:qualityScore')
        report = validate_quality_score(quality)
        blockers.extend(f'quality:{x}' for x in report.get('blockers', []))
        warnings.extend(f'quality:{x}' for x in report.get('warnings', []))

    expected = expected_design_state(handoff)
    if handoff.get('designState') != expected:
        blockers.append(f'DESIGN_STATE_MISMATCH:{handoff.get("designState")}!={expected}')

    evidence = handoff.get('privateConversationEvidence')
    if evidence and evidence.get('detailPublished') is not False:
        blockers.append('CONVERSATION_DETAIL_MUST_NOT_BE_PUBLIC')

    return {
        'status':'FAIL' if blockers else 'PASS',
        'courseId':cid,
        'designState':expected,
        'approvedSessions':approved_sessions,
        'blockers':sorted(set(blockers)),
        'warnings':sorted(set(warnings)),
    }


def materialize_handoff(handoff, out_dir: Path):
    report = validate_handoff(handoff)
    if report['status'] != 'PASS':
        raise QAError('handoff validation failed: ' + '; '.join(report['blockers']))
    if handoff['designState'] != 'ALL_CONTENT_APPROVED':
        raise QAError('materialize requires ALL_CONTENT_APPROVED')
    if out_dir.exists() and any(out_dir.iterdir()):
        raise QAError(f'materialize target must be empty: {out_dir}')
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'storyboards').mkdir()

    def write(name, value):
        (out_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    write('source-policy.json', handoff['sourcePolicy'])
    write('course-map.json', handoff['courseMap'])
    write('concept-policy.json', handoff['conceptPolicy'])
    write('quality-score.json', handoff['qualityScore'])
    for storyboard in handoff['storyboards']:
        write(f'storyboards/session-{storyboard["session"]}.json', storyboard)

    bundle_report = check_bundle(out_dir)
    if bundle_report['status'] != 'PASS':
        shutil.rmtree(out_dir, ignore_errors=True)
        raise QAError('materialized Factory bundle failed: ' + '; '.join(bundle_report.get('blockers', [])))
    return {'status':'PASS','outDir':str(out_dir),'contentDesign':bundle_report}


def main():
    parser = argparse.ArgumentParser(prog='handoff')
    sub = parser.add_subparsers(dest='cmd', required=True)
    v = sub.add_parser('validate')
    v.add_argument('--file', required=True)
    v.add_argument('--json', dest='jsonout')
    m = sub.add_parser('materialize')
    m.add_argument('--file', required=True)
    m.add_argument('--out', required=True)
    args = parser.parse_args()

    try:
        handoff = load_jsonish(Path(args.file))
        report = validate_handoff(handoff) if args.cmd == 'validate' else materialize_handoff(handoff, Path(args.out))
        text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if getattr(args, 'jsonout', None):
            out = Path(args.jsonout)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding='utf-8')
        print(text, end='')
        raise SystemExit(0 if report['status'] == 'PASS' else 2)
    except (QAError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({'status':'FAIL','error':str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(2)


if __name__ == '__main__':
    main()
