#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core import ROOT, check_schema_subset, load_jsonish

SCHEMA = ROOT / 'contracts' / 'design-proof.schema.json'
REQUIRED_ARTIFACT_ROLES = {'final-package','presentation','practice-tool','activity-pack','media'}


def validate_design_proof(proof: dict, expected_course_id: str | None = None):
    blockers = [f'SCHEMA:{e}' for e in check_schema_subset(proof, load_jsonish(SCHEMA))]
    warnings = []

    if expected_course_id and proof.get('courseId') != expected_course_id:
        blockers.append('DESIGN_PROOF_COURSE_ID_MISMATCH')

    sources = proof.get('sources', [])
    source_ids = [x.get('id') for x in sources if isinstance(x, dict)]
    if len(source_ids) != len(set(source_ids)):
        blockers.append('DESIGN_PROOF_SOURCE_ID_DUPLICATE')

    course_sessions = proof.get('courseMap', {}).get('sessions', [])
    metrics = proof.get('sessionMetrics', [])
    course_numbers = [x.get('session') for x in course_sessions if isinstance(x, dict)]
    metric_numbers = [x.get('session') for x in metrics if isinstance(x, dict)]
    expected_numbers = list(range(1, len(course_numbers) + 1))
    if course_numbers != expected_numbers:
        blockers.append('DESIGN_PROOF_SESSION_NUMBERS_NOT_CONTIGUOUS')
    if metric_numbers != course_numbers:
        blockers.append('DESIGN_PROOF_SESSION_METRICS_MISMATCH')
    for item in metrics:
        if float(item.get('fullMinutes', 0) or 0) < float(item.get('coreMinutes', 0) or 0):
            blockers.append(f'DESIGN_PROOF_FULL_TIME_LT_CORE:SESSION_{item.get("session")}')
        if int(item.get('coreSlides', 0) or 0) + int(item.get('bufferSlides', 0) or 0) < 1:
            blockers.append(f'DESIGN_PROOF_SLIDES_EMPTY:SESSION_{item.get("session")}')

    quality = proof.get('quality', {})
    domains = quality.get('domains', {})
    if domains:
        calculated = sum(float(v) for v in domains.values())
        if abs(calculated - float(quality.get('overall', -1))) > 1e-9:
            blockers.append(f'DESIGN_PROOF_QUALITY_TOTAL_MISMATCH:{calculated}!={quality.get("overall")}')
    if quality.get('hardGatesPass') is not True:
        blockers.append('DESIGN_PROOF_HARD_GATES_NOT_PASS')

    artifacts = proof.get('artifacts', [])
    roles = [x.get('role') for x in artifacts if isinstance(x, dict)]
    if len(roles) != len(set(roles)):
        blockers.append('DESIGN_PROOF_ARTIFACT_ROLE_DUPLICATE')
    missing = sorted(REQUIRED_ARTIFACT_ROLES - set(roles))
    if missing:
        blockers.append('DESIGN_PROOF_ARTIFACT_ROLE_MISSING:' + ','.join(missing))

    qa = proof.get('qa', {})
    if qa.get('pptxRenderPass') is not True:
        blockers.append('DESIGN_PROOF_PPTX_RENDER_NOT_PASS')
    if qa.get('pptxOverflowCount') != 0:
        blockers.append('DESIGN_PROOF_PPTX_OVERFLOW')
    if qa.get('pptxNotes') != qa.get('pptxSlides'):
        blockers.append('DESIGN_PROOF_PPTX_NOTES_INCOMPLETE')
    if qa.get('htmlOffline') is not True or qa.get('htmlExternalRuntimeRefs') != 0:
        blockers.append('DESIGN_PROOF_HTML_OFFLINE_NOT_PASS')
    if qa.get('manualChecksPending'):
        warnings.append('DESIGN_PROOF_MANUAL_CHECKS_PENDING:' + ','.join(qa['manualChecksPending']))

    if proof.get('visibility') == 'summary-only-public' and proof.get('privateEvidence', {}).get('detailPublished') is not False:
        blockers.append('DESIGN_PROOF_PRIVATE_DETAIL_EXPOSED')

    rights = proof.get('rights', {})
    if rights.get('publicDistributionApproved') is not True:
        warnings.append('DESIGN_PROOF_PUBLIC_DISTRIBUTION_NOT_APPROVED')

    return {
        'status': 'FAIL' if blockers else 'PASS',
        'courseId': proof.get('courseId'),
        'designVersion': proof.get('designVersion'),
        'blockers': blockers,
        'warnings': warnings,
        'qualityOverall': quality.get('overall'),
        'sessions': len(course_sessions),
        'artifacts': roles,
    }


def verify_path(path: Path, expected_course_id: str | None = None):
    proof = load_jsonish(path)
    return validate_design_proof(proof, expected_course_id)


def main():
    parser = argparse.ArgumentParser(prog='design_proof')
    parser.add_argument('proof')
    parser.add_argument('--course')
    args = parser.parse_args()
    report = verify_path(Path(args.proof), args.course)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['status'] == 'PASS' else 2)


if __name__ == '__main__':
    main()
