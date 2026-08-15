from __future__ import annotations
import re
from pathlib import Path
from core import QAError, load_jsonish, sha256

CHECKSUM_RE = re.compile(r'^([0-9a-f]{64})  (.+)$')


def parse_checksums(path: Path):
    entries = {}
    for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        match = CHECKSUM_RE.fullmatch(line)
        if not match:
            raise QAError(f'invalid checksum line {lineno}')
        digest, name = match.groups()
        if name in entries:
            raise QAError(f'duplicate checksum entry: {name}')
        entries[name] = digest
    return entries


def verify_inventory(base: Path, manifest_path: Path, checksum_path: Path):
    manifest = load_jsonish(manifest_path)
    assets = manifest.get('assets')
    if not isinstance(assets, list) or not assets:
        raise QAError('manifest assets missing')
    files = [a.get('file') for a in assets]
    if any(not isinstance(x, str) or not x for x in files):
        raise QAError('manifest asset file invalid')
    if len(files) != len(set(files)):
        raise QAError('duplicate manifest asset path')
    checksums = parse_checksums(checksum_path)
    expected_checksums = set(files) | {manifest_path.name}
    if set(checksums) != expected_checksums:
        missing = sorted(expected_checksums - set(checksums))
        extra = sorted(set(checksums) - expected_checksums)
        raise QAError(f'checksum inventory mismatch missing={missing} extra={extra}')
    expected_root = set(files) | {manifest_path.name, checksum_path.name}
    actual_root = {p.name for p in base.iterdir() if p.is_file()}
    if actual_root != expected_root:
        missing = sorted(expected_root - actual_root)
        extra = sorted(actual_root - expected_root)
        raise QAError(f'package root inventory mismatch missing={missing} extra={extra}')
    for asset in assets:
        path = base / asset['file']
        if not path.is_file():
            raise QAError('missing asset: ' + asset['file'])
        if path.stat().st_size != asset.get('size'):
            raise QAError('asset size mismatch: ' + asset['file'])
        if sha256(path) != asset.get('sha256'):
            raise QAError('asset SHA mismatch: ' + asset['file'])
        if checksums[asset['file']] != asset['sha256']:
            raise QAError('checksum/manifest SHA mismatch: ' + asset['file'])
    if checksums[manifest_path.name] != sha256(manifest_path):
        raise QAError('manifest checksum mismatch')
    return {'assetCount': len(assets), 'checksumCount': len(checksums), 'rootFileCount': len(actual_root)}


def _extract_runtime_constants(text: str):
    combined = re.search(
        r"const\s+APP_VERSION='([^']+)',BUILD_ID='([^']+)',SCHEMA_VERSION=(\d+),DATASET_VERSION='([^']+)'\s*;",
        text,
    )
    source = re.search(r"const\s+SOURCE_SHA256='([0-9a-f]{64})'\s*;", text)
    store = re.search(r"const\s+STORE_KEY='([^']+)'\s*;", text)
    if not combined or not source or not store:
        raise QAError('runtime metadata constants missing')
    return {
        'appVersion': combined.group(1),
        'buildId': combined.group(2),
        'schemaVersion': int(combined.group(3)),
        'datasetVersion': combined.group(4),
        'sourceSha256': source.group(1),
        'storeKey': store.group(1),
    }


def html_runtime_contract(path: Path, manifest: dict):
    text = path.read_text(encoding='utf-8')
    meta = _extract_runtime_constants(text)
    runtime = manifest.get('runtime', {})
    expected = {
        'appVersion': runtime.get('appVersion'),
        'buildId': runtime.get('buildId'),
        'schemaVersion': runtime.get('schemaVersion'),
        'datasetVersion': runtime.get('datasetVersion'),
    }
    for key, value in expected.items():
        if meta[key] != value:
            raise QAError(f'HTML/manifest runtime metadata mismatch: {key}')
    original = manifest.get('source', {}).get('originalSimulatorSha256')
    if original and meta['sourceSha256'] != original:
        raise QAError('HTML original source SHA provenance mismatch')
    ids = re.findall(r'\bid=["\']([^"\']+)["\']', text)
    dup = sorted({x for x in ids if ids.count(x) > 1})
    if dup:
        raise QAError('duplicate HTML ids: ' + ','.join(dup))
    required_ids = {'reset','import','importFile','export','print','run','reveal','mainPrediction'}
    missing = sorted(required_ids - set(ids))
    if missing:
        raise QAError('required runtime controls missing: ' + ','.join(missing))
    if 'localStorage' in text:
        raise QAError('localStorage forbidden; session-only storage required')
    required_tokens = [
        'sessionStorage.setItem',
        'sessionStorage.getItem',
        'URL.createObjectURL',
        'new Blob(',
        "type='file'" if "type='file'" in text else 'type="file"',
        'window.print()',
        'validateEnvelope',
        'sanitizedPayload',
        'configurationChanged',
        'stateAfterPredictionEdit',
    ]
    absent = [token for token in required_tokens if token not in text]
    if absent:
        raise QAError('runtime capability contract missing: ' + ','.join(absent))
    if not re.search(r'@media\s+print', text):
        raise QAError('print stylesheet missing')
    return {'metadata': meta, 'idCount': len(ids), 'requiredControls': sorted(required_ids), 'sessionOnly': True, 'printCss': True}


def runtime_report_contract(report_path: Path, html_asset: dict, manifest: dict, expected: dict):
    report = load_jsonish(report_path)
    runtime = manifest.get('runtime', {})
    qa = manifest.get('qa', {}).get('runtime', {})
    if report.get('status') != 'PASS' or report.get('failures'):
        raise QAError('runtime report not PASS')
    if report.get('sha256') != html_asset.get('sha256') or qa.get('subjectSha256') != html_asset.get('sha256'):
        raise QAError('runtime report subject SHA mismatch')
    versions = report.get('versions', {})
    mapping = {'app': 'appVersion', 'build': 'buildId', 'schema': 'schemaVersion', 'dataset': 'datasetVersion'}
    for report_key, manifest_key in mapping.items():
        if versions.get(report_key) != runtime.get(manifest_key):
            raise QAError('runtime report version mismatch: ' + report_key)
    checks = report.get('checks', {})
    if len(checks) != expected['runtimeChecks']['total'] or not checks or not all(v is True for v in checks.values()):
        raise QAError('runtime report check matrix mismatch')
    if qa.get('checks') != expected['runtimeChecks']['total']:
        raise QAError('manifest runtime check count mismatch')
    details = report.get('details', {})
    if details.get('matrixCases') != expected['runtimeChecks']['supportedMatrixTotal'] or details.get('matrixFailures'):
        raise QAError('runtime supported matrix mismatch')
    required_checks = {
        'externalDependencies','networkApis','sessionOnlyStorage','importSchemaRejected','importBooleanTypesRejected',
        'importWeightTypesRejected','nestedEvidenceRejected','importRoundTripEvidence','staleTestInvalidation',
        'predictionReasonGate','predictionEditInvalidates','mainPredictionStateTransition','finalOnlyPrintCss'
    }
    missing = sorted(required_checks - set(checks))
    if missing:
        raise QAError('runtime report required checks missing: ' + ','.join(missing))
    return {'checkCount': len(checks), 'matrixCases': details.get('matrixCases'), 'requiredChecksPresent': len(required_checks)}


def manifest_contract(manifest: dict, golden: dict, budget_policy: dict):
    expected = golden['expected']
    if manifest.get('manifestSchemaVersion') != '1.0.0':
        raise QAError('unexpected package manifest schema version')
    if manifest.get('version') != golden.get('packageVersion'):
        raise QAError('package version mismatch')
    if manifest.get('stage') != expected.get('stage') or manifest.get('nextStageCandidate') != expected.get('nextStageCandidate'):
        raise QAError('package stage contract mismatch')
    if manifest.get('releaseDecision') != expected.get('releaseDecision'):
        raise QAError('package releaseDecision mismatch')
    runtime = manifest.get('runtime', {})
    qa = manifest.get('qa', {})
    if qa.get('runtime', {}).get('status') != 'PASS':
        raise QAError('manifest runtime QA is not PASS')
    if qa.get('prototypePptx', {}).get('slides') != expected['prototype']['slides'] or qa.get('prototypePptx', {}).get('notes') != expected['prototype']['notes']:
        raise QAError('manifest prototype slide/note mismatch')
    if qa.get('prototypePptx', {}).get('overflow') != expected['prototype']['overflow']:
        raise QAError('manifest prototype overflow mismatch')
    cost = manifest.get('costPolicy', {})
    pairs = {
        'monthlyIncrementalBudgetUsd': 'monthlyIncrementalBudgetUsd',
        'allowLargerRunners': 'allowLargerRunners',
        'allowWorkersPaid': 'allowWorkersPaid',
        'allowCloudflareContainers': 'allowCloudflareContainers',
    }
    for mk, pk in pairs.items():
        if cost.get(mk) != budget_policy.get(pk):
            raise QAError('package/budget policy mismatch: ' + mk)
    assets = manifest.get('assets', [])
    roles = [a.get('role') for a in assets]
    if len(roles) != len(set(roles)):
        raise QAError('duplicate asset role')
    required_roles = {
        'readme','runtime-test-runner','package-validator','operating-specification','prototype-presentation',
        'prototype-qa-report','prototype-render-evidence','prototype-preview','student-runtime','qa-decision',
        'static-answer-key','evidence-pitch-rubric','instructor-preflight','team-record-sheet','runtime-qa-report'
    }
    missing = sorted(required_roles - set(roles))
    if missing:
        raise QAError('required package roles missing: ' + ','.join(missing))
    if manifest.get('distribution', {}).get('currentPackagePublicCommitAllowed') is not False:
        raise QAError('rights-unverified package must not be public-commit allowed')
    if manifest.get('quality', {}).get('status') != 'NOT_SCORED' or manifest.get('rights', {}).get('status') != 'UNVERIFIED':
        raise QAError('golden package HOLD quality/rights contract changed unexpectedly')
    return {'assetRoles': len(roles), 'stage': manifest['stage'], 'releaseDecision': manifest['releaseDecision'], 'runtime': runtime}
