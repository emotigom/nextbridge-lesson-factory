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

GATE_METRIC_RULES = {
    'BROWSER_FILE_SMOKE': {
        'chromePass': ('true', None),
        'edgePass': ('true', None),
        'chromeConsoleErrors': ('eq', 0),
        'edgeConsoleErrors': ('eq', 0),
        'fileProtocolPass': ('true', None),
    },
    'VIEWPORT_1440_900_375_812': {
        'desktop1440x900Pass': ('true', None),
        'mobile375x812Pass': ('true', None),
    },
    'JSON_ROUNDTRIP_PRINT': {
        'jsonDownloadPass': ('true', None),
        'newTeamResetPass': ('true', None),
        'jsonImportPass': ('true', None),
        'printPreviewPass': ('true', None),
        'printClippingCount': ('eq', 0),
    },
    'WINDOWS_POWERPOINT_SMOKE': {
        'openPass': ('true', None),
        'notesPass': ('true', None),
        'slideshowPass': ('true', None),
        'pdfExportPass': ('true', None),
        'saveReopenPass': ('true', None),
        'recoveryDialogCount': ('eq', 0),
    },
    'FONT_PORTABILITY_REFLOW': {
        'cleanMachinePass': ('true', None),
        'missingGlyphCount': ('eq', 0),
        'reflowApproved': ('true', None),
    },
    'INDEPENDENT_INSTRUCTOR_REHEARSAL': {
        'plannedMinutes': ('positive', None),
        'actualMinutes': ('positive', None),
        'rescueWithin3MinPass': ('true', None),
    },
    'STUDENT_FIELD_PILOT': {
        'minimumOutputCompletionPct': ('min', 85),
        'saveSubmitSuccessPct': ('min', 90),
        'privacyCriticalIncidentCount': ('eq', 0),
    },
}


def evidence_schema():
    return load_jsonish(ROOT / 'contracts/manual-evidence.schema.json')


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def metric_blockers(gate: str, metrics: dict):
    rules = GATE_METRIC_RULES.get(gate, {})
    blockers = []
    if not isinstance(metrics, dict):
        return ['EVIDENCE_METRICS_MISSING']
    for name, (rule, limit) in rules.items():
        if name not in metrics:
            blockers.append('EVIDENCE_METRIC_MISSING:' + name)
            continue
        value = metrics[name]
        if rule == 'true' and value is not True:
            blockers.append('EVIDENCE_METRIC_NOT_TRUE:' + name)
        elif rule == 'eq' and (not _is_number(value) or value != limit):
            blockers.append(f'EVIDENCE_METRIC_NOT_{limit}:{name}')
        elif rule == 'min' and (not _is_number(value) or value < limit):
            blockers.append(f'EVIDENCE_METRIC_BELOW_{limit}:{name}')
        elif rule == 'positive' and (not _is_number(value) or value <= 0):
            blockers.append('EVIDENCE_METRIC_NOT_POSITIVE:' + name)
    if gate == 'INDEPENDENT_INSTRUCTOR_REHEARSAL':
        planned = metrics.get('plannedMinutes') if isinstance(metrics, dict) else None
        actual = metrics.get('actualMinutes') if isinstance(metrics, dict) else None
        if _is_number(planned) and _is_number(actual) and planned > 0 and abs(actual - planned) / planned > 0.10:
            blockers.append('EVIDENCE_REHEARSAL_OUTSIDE_10_PERCENT')
    return blockers


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
    else:
        blockers.extend(metric_blockers(gate, evidence.get('metrics')))
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


def evidence_plan(course_id: str):
    course = load_jsonish(course_path(course_id))
    gates = []
    for gate in REQUIRED_MANUAL_GATES:
        subject = manual_gate_subject(course, gate)
        gates.append({
            'gate': gate,
            'subjectSha256': subject,
            'requiredMetrics': sorted(GATE_METRIC_RULES[gate]),
            'status': next((g['status'] for g in course['manualGates'] if g['id'] == gate), 'PENDING'),
        })
    return {'schemaVersion':'1.0.0','courseId':course_id,'stage':course['stage'],'releaseDecision':course['releaseDecision'],'gates':gates}


def _template_metric_value(rule: str, limit):
    if rule == 'true':
        return False
    if rule == 'eq':
        return -1 if limit == 0 else None
    if rule in ('min', 'positive'):
        return 0
    return None


def evidence_template(course: dict, gate: str):
    if gate not in GATE_METRIC_RULES:
        raise QAError(f'unknown manual gate: {gate}')
    subject = manual_gate_subject(course, gate)
    if not subject:
        raise QAError(f'cannot resolve subject for gate {gate}')
    metrics = {
        name: _template_metric_value(rule, limit)
        for name, (rule, limit) in GATE_METRIC_RULES[gate].items()
    }
    return {
        'schemaVersion': '1.0.0',
        'courseId': course['courseId'],
        'gate': gate,
        'status': 'FAIL',
        'subjectSha256': subject,
        'capturedAt': 'RECORD_AFTER_TEST',
        'reviewer': 'RECORD_REVIEWER',
        'environment': {'platform': 'RECORD_PLATFORM'},
        'evidenceRefs': ['RECORD_PRIVATE_EVIDENCE_REF'],
        'metrics': metrics,
        'notes': 'Template only. Keep FAIL until the real test is completed and every metric is measured.',
    }


def scaffold_evidence(course_id: str, out_dir: Path):
    import json
    course = load_jsonish(course_path(course_id))
    if out_dir.exists() and any(out_dir.iterdir()):
        raise QAError(f'evidence scaffold target must be empty: {out_dir}')
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = evidence_plan(course_id)
    (out_dir / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for gate in REQUIRED_MANUAL_GATES:
        record = evidence_template(course, gate)
        (out_dir / f'{gate}.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    readme = (
        f'# Manual Gate evidence kit — {course_id}\n\n'
        'Generated from the current source lock. Every template intentionally starts with `status: FAIL`.\n\n'
        '1. Run the real test described in `docs/gates/manual-evidence.md`.\n'
        '2. Replace environment/reviewer/evidenceRefs and measured metrics.\n'
        '3. Change `status` to `PASS` only after measurements meet the gate contract.\n'
        f'4. Verify each file with `./lessonctl evidence verify --course {course_id} --file <file>`.\n'
        f'5. Before promotion, run `./lessonctl stage check --course {course_id} --to <NEXT_STAGE> --evidence-dir <this-directory>`.\n\n'
        'Do not store real school/student evidence in public Git.\n'
    )
    (out_dir / 'README.md').write_text(readme, encoding='utf-8')
    return {'courseId': course_id, 'outDir': str(out_dir), 'templates': len(REQUIRED_MANUAL_GATES), 'status': 'SCAFFOLDED_FAIL_SAFE'}
