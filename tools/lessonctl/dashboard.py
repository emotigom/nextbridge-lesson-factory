from __future__ import annotations
import json
from pathlib import Path
from core import ROOT, golden_check, load_jsonish

GATE_LABELS = {
    'BROWSER_FILE_SMOKE': 'Browser file:// smoke',
    'VIEWPORT_1440_900_375_812': 'Desktop/mobile viewport',
    'JSON_ROUNDTRIP_PRINT': 'JSON roundtrip + print',
    'WINDOWS_POWERPOINT_SMOKE': 'Windows PowerPoint smoke',
    'FONT_PORTABILITY_REFLOW': 'Font portability + reflow',
    'INDEPENDENT_INSTRUCTOR_REHEARSAL': 'Independent instructor rehearsal',
    'STUDENT_FIELD_PILOT': 'Student field pilot',
}


def course_blockers(course: dict):
    blockers = []
    if course.get('ssot', {}).get('syncStatus') != 'SYNCED':
        blockers.append('SSOT_' + course.get('ssot', {}).get('syncStatus', 'UNKNOWN'))
    quality = course.get('quality', {})
    if quality.get('status') != 'SCORED' or quality.get('overall') is None:
        blockers.append('QUALITY_NOT_SCORED')
    if course.get('rights', {}).get('status') != 'VERIFIED':
        blockers.append('RIGHTS_UNVERIFIED')
    if any(g.get('status') != 'PASS' for g in course.get('manualGates', [])):
        blockers.append('MANUAL_GATES_PENDING')
    return sorted(set(blockers))


def status_payload(course: dict):
    ok, _, golden = golden_check(course)
    expected = golden['expected']
    runtime = expected['runtimeChecks']
    prototype = expected['prototype']
    gates = [
        {
            'id': 'GOLDEN_RUNTIME',
            'name': 'Golden runtime',
            'status': 'PASS' if ok else 'FAIL',
            'detail': f"{runtime['passed']}/{runtime['total']} · matrix {runtime['supportedMatrixPassed']}/{runtime['supportedMatrixTotal']}",
        },
        {
            'id': 'GOLDEN_PROTOTYPE',
            'name': '5장 prototype',
            'status': 'PASS' if ok and prototype['visibleRenderPixelEqual'] and prototype['overflow'] == 0 else 'FAIL',
            'detail': f"{prototype['slides']} slides · {prototype['notes']} notes · overflow {prototype['overflow']}",
        },
        {
            'id': 'SSOT_SYNC',
            'name': 'SSOT sync',
            'status': 'PASS' if course['ssot']['syncStatus'] == 'SYNCED' else 'HOLD',
            'detail': course['ssot']['syncStatus'],
        },
        {
            'id': 'QUALITY_SCORE',
            'name': 'Quality score',
            'status': 'PASS' if course['quality']['status'] == 'SCORED' and course['quality']['overall'] is not None else 'PENDING',
            'detail': 'not scored' if course['quality']['overall'] is None else str(course['quality']['overall']),
        },
        {
            'id': 'RIGHTS',
            'name': 'Rights',
            'status': 'PASS' if course['rights']['status'] == 'VERIFIED' else 'PENDING',
            'detail': course['rights']['status'],
        },
    ]
    for gate in course['manualGates']:
        gates.append({
            'id': gate['id'],
            'name': GATE_LABELS.get(gate['id'], gate['id']),
            'status': gate['status'],
            'detail': 'invalidates on ' + ', '.join(gate['invalidateOn']),
        })
    return {
        'schemaVersion': '1.0.0',
        'courseId': course['courseId'],
        'title': course['title'],
        'version': course['version'],
        'stage': course['stage'],
        'releaseDecision': course['releaseDecision'],
        'promotionBlockers': course_blockers(course),
        'gates': gates,
    }


def releases_payload(course: dict):
    return {
        'schemaVersion': '1.0.0',
        'releases': [{
            'courseId': course['courseId'],
            'version': course['version'],
            'stage': course['stage'],
            'releaseDecision': course['releaseDecision'],
            'publicArtifacts': [],
        }],
    }


def canonical_json(data: dict):
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def build_dashboard(course: dict, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'status.json').write_text(canonical_json(status_payload(course)), encoding='utf-8')
    (out_dir / 'releases.json').write_text(canonical_json(releases_payload(course)), encoding='utf-8')


def verify_dashboard(course: dict, out_dir: Path | None = None):
    out_dir = out_dir or ROOT / 'apps/dashboard/data'
    expected = {
        'status.json': canonical_json(status_payload(course)),
        'releases.json': canonical_json(releases_payload(course)),
    }
    drift = []
    for name, content in expected.items():
        path = out_dir / name
        if not path.is_file():
            drift.append(name + ':missing')
        elif path.read_text(encoding='utf-8') != content:
            drift.append(name + ':drift')
    return (not drift, 'dashboard data matches course contract' if not drift else 'dashboard drift: ' + ', '.join(drift))
