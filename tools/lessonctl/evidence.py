from __future__ import annotations
from pathlib import Path
from core import ROOT, STAGES, QAError, check_schema_subset, course_path, load_jsonish
from release_policy import manual_gate_subject

REQUIRED_MANUAL_GATES = (
    'BROWSER_FILE_SMOKE',
    'VIEWPORT_1440_900_375_812',
    'JSON_ROUNDTRIP_PRINT',
    'WINDOWS_POWERPOINT_SMOKE',
    'FONT_PORTABILITY_REFLOW',
    'INDEPENDENT_INSTRUCTOR_REHEARSAL',
    'STUDENT_FIELD_PILOT',
)

STAGE_GATE_REQUIREMENTS = {
    'INSTRUCTOR_PILOT': REQUIRED_MANUAL_GATES[:5],
    'FIELD_PILOT': REQUIRED_MANUAL_GATES[:6],
    'FIELD_READY': REQUIRED_MANUAL_GATES,
    'CANONICAL': REQUIRED_MANUAL_GATES,
}


def evidence_schema():
    return load_jsonish(ROOT / 'contracts/manual-evidence.schema.json')


def verify_evidence(course: dict, evidence: dict):
    errors = check_schema_subset(evidence, evidence_schema())
    if errors:
        return False, ['EVIDENCE_SCHEMA:' + e for e in errors]
    blockers = []
    if evidence.get('courseId') != course.get('courseId'):
        blockers.append('EVIDENCE_COURSE_MISMATCH')
    gate = evidence.get('gate')
    gate_contract = next((g for g in course.get('manualGates', []) if g.get('id') == gate), None)
    if gate_contract is None:
        blockers.append('EVIDENCE_GATE_NOT_IN_COURSE')
    expected = manual_gate_subject(course, gate)
    if not expected:
        blockers.append('EVIDENCE_SUBJECT_UNRESOLVED')
    elif evidence.get('subjectSha256') != expected:
        blockers.append('EVIDENCE_STALE_SUBJECT')
    if evidence.get('status') != 'PASS':
        blockers.append('EVIDENCE_NOT_PASS')
    return not blockers, blockers


def load_evidence_dir(course: dict, evidence_dir: Path):
    if not evidence_dir.is_dir():
        raise QAError(f'evidence directory not found: {evidence_dir}')
    records = {}
    findings = []
    for path in sorted(evidence_dir.glob('*.json')):
        try:
            record = load_jsonish(path)
        except Exception as exc:
            findings.append(f'EVIDENCE_PARSE:{path.name}:{exc}')
            continue
        gate = record.get('gate')
        if gate in records:
            findings.append(f'EVIDENCE_DUPLICATE_GATE:{gate}')
            continue
        ok, blockers = verify_evidence(course, record)
        records[gate] = record
        findings.extend(f'{gate}:{b}' for b in blockers)
    return records, findings


def stage_check(course: dict, target_stage: str, evidence_dir: Path | None = None):
    blockers = []
    current = course.get('stage')
    if current not in STAGES or target_stage not in STAGES:
        return ['INVALID_STAGE']
    current_index = STAGES.index(current)
    target_index = STAGES.index(target_stage)
    if target_index < current_index:
        blockers.append('STAGE_REGRESSION_FORBIDDEN')
    elif target_index > current_index + 1:
        blockers.append('STAGE_SKIP_FORBIDDEN')
    elif target_index == current_index:
        return []

    required = STAGE_GATE_REQUIREMENTS.get(target_stage, ())
    if required:
        if evidence_dir is None:
            blockers.append('MANUAL_EVIDENCE_DIR_REQUIRED')
            records = {}
            findings = []
        else:
            records, findings = load_evidence_dir(course, evidence_dir)
            blockers.extend(findings)
        for gate in required:
            if gate not in records:
                blockers.append('MANUAL_GATE_EVIDENCE_MISSING:' + gate)

    if target_stage in ('FIELD_READY', 'CANONICAL'):
        quality = course.get('quality', {})
        if quality.get('status') != 'SCORED' or quality.get('overall') is None or quality.get('overall') < 90:
            blockers.append('QUALITY_BELOW_90_OR_UNSCORED')
        domains = quality.get('domains', {})
        if not domains:
            blockers.append('QUALITY_DOMAINS_MISSING')
        for name, score in domains.items():
            if not isinstance(score, (int, float)) or isinstance(score, bool) or score < 80:
                blockers.append('QUALITY_DOMAIN_BELOW_80:' + name)
        rights = course.get('rights', {})
        if rights.get('status') != 'VERIFIED' or not rights.get('publicDistributionApproved'):
            blockers.append('RIGHTS_NOT_APPROVED')
        if course.get('ssot', {}).get('syncStatus') != 'SYNCED':
            blockers.append('SSOT_NOT_SYNCED')
    if target_stage == 'CANONICAL' and course.get('releaseDecision') != 'APPROVED':
        blockers.append('CANONICAL_REQUIRES_RELEASE_APPROVED')
    return sorted(set(blockers))


def evidence_subject(course_id: str, gate: str):
    course = load_jsonish(course_path(course_id))
    subject = manual_gate_subject(course, gate)
    if not subject:
        raise QAError(f'cannot resolve subject for gate {gate}')
    return subject
