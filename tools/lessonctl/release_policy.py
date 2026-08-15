from __future__ import annotations
import hashlib, re, tempfile, zipfile
from pathlib import Path, PurePosixPath
from core import ROOT, STAGES, SHA_RE, QAError, load_jsonish, sha256, check_schema_subset, course_path, wip_check

def manual_gate_subject(course,gate_id):
    gate=next((g for g in course.get('manualGates',[]) if g.get('id')==gate_id),None)
    if not gate: return None
    vals=[]
    for dep in gate.get('invalidateOn',[]):
        v=course.get('sourceLock',{}).get(dep)
        if not v: return None
        vals.append(v)
    if not vals: return None
    if len(vals)==1: return vals[0]
    return hashlib.sha256(('\n'.join(vals)).encode('ascii')).hexdigest()

def release_policy(manifest,require_approved=False):
    blockers=[]
    if manifest.get('releaseDecision')!='APPROVED': blockers.append('RELEASE_DECISION_NOT_APPROVED')
    try:
        if STAGES.index(manifest.get('stage','DRAFT'))<STAGES.index('FIELD_READY'): blockers.append('STAGE_BELOW_FIELD_READY')
    except ValueError: blockers.append('INVALID_STAGE')
    q=manifest.get('quality',{}); overall=q.get('overall'); domains=q.get('domains',{})
    if overall is None or overall<90: blockers.append('QUALITY_BELOW_90_OR_UNSCORED')
    if not domains: blockers.append('QUALITY_DOMAINS_MISSING')
    for name,score in domains.items():
        if not isinstance(score,(int,float)) or isinstance(score,bool) or score<80: blockers.append('QUALITY_DOMAIN_BELOW_80:'+name)
    rights=manifest.get('rights',{})
    if rights.get('status')!='VERIFIED' or not rights.get('publicDistributionApproved'): blockers.append('RIGHTS_NOT_APPROVED')
    approval=manifest.get('approval',{})
    if not approval.get('reviewer') or not approval.get('approvedAt'): blockers.append('HUMAN_APPROVAL_MISSING')
    if manifest.get('ssot',{}).get('status')!='SYNCED': blockers.append('SSOT_NOT_SYNCED')
    fm=manifest.get('fieldMetrics',{}); rehearsal=fm.get('instructorRehearsal',{}); pilot=fm.get('studentPilot',{}); planned=rehearsal.get('plannedMinutes'); actual=rehearsal.get('actualMinutes')
    if not isinstance(planned,(int,float)) or not isinstance(actual,(int,float)) or planned<=0: blockers.append('INSTRUCTOR_REHEARSAL_TIME_MISSING')
    elif abs(actual-planned)/planned>0.10: blockers.append('INSTRUCTOR_REHEARSAL_OUTSIDE_10_PERCENT')
    completion=pilot.get('minimumOutputCompletionPct'); submit=pilot.get('saveSubmitSuccessPct'); incidents=pilot.get('privacyCriticalIncidentCount')
    if not isinstance(completion,(int,float)) or completion<85: blockers.append('STUDENT_OUTPUT_COMPLETION_BELOW_85_OR_MISSING')
    if not isinstance(submit,(int,float)) or submit<90: blockers.append('SAVE_SUBMIT_SUCCESS_BELOW_90_OR_MISSING')
    if not isinstance(incidents,int) or isinstance(incidents,bool) or incidents!=0: blockers.append('PRIVACY_OR_CRITICAL_INCIDENT_NONZERO_OR_MISSING')
    required_gates={'BROWSER_FILE_SMOKE','VIEWPORT_1440_900_375_812','JSON_ROUNDTRIP_PRINT','WINDOWS_POWERPOINT_SMOKE','FONT_PORTABILITY_REFLOW','INDEPENDENT_INSTRUCTOR_REHEARSAL','STUDENT_FIELD_PILOT'}; evidence={e.get('gate'):e for e in manifest.get('manualEvidence',[])}
    for gate in sorted(required_gates):
        if gate not in evidence: blockers.append('MANUAL_GATE_MISSING:'+gate)
        elif evidence[gate].get('status')!='PASS': blockers.append('MANUAL_GATE_NOT_PASS:'+gate)
    if require_approved and blockers: raise QAError('release blocked: '+', '.join(blockers))
    return blockers

def r2_key(course_id,version,sha,filename):
    if not SHA_RE.match(sha): raise QAError('invalid sha for R2 key')
    fn=PurePosixPath(filename).name
    if fn!=filename or fn in ('','.','..'): raise QAError('unsafe filename')
    return f'courses/{course_id}/{version}/{sha}/{fn}'

def verify_manifest(manifest_path:Path,root_dir:Path|None,require_approved=False):
    m=load_jsonish(manifest_path); errs=check_schema_subset(m,load_jsonish(ROOT/'contracts/release.schema.json'))
    if errs: raise QAError('release schema: '+'; '.join(errs))
    if root_dir:
        for a in m['assets']:
            p=root_dir/a['file']
            if not p.is_file(): raise QAError('missing asset '+a['file'])
            if p.stat().st_size!=a['size'] or sha256(p)!=a['sha256']: raise QAError('asset integrity mismatch '+a['file'])
            a['r2Key']=r2_key(m['courseId'],m['version'],a['sha256'],a['file'])
    blockers=release_policy(m); cp=course_path(m['courseId'])
    if cp.is_file():
        course=load_jsonish(cp); ok,_=wip_check(course)
        if not ok: blockers.append('WIP_CONTRACT_MISMATCH')
        if course.get('stage')!=m.get('stage'): blockers.append('COURSE_RELEASE_STAGE_MISMATCH')
        if course.get('releaseDecision')!=m.get('releaseDecision'): blockers.append('COURSE_RELEASE_DECISION_MISMATCH')
        if course.get('ssot',{}).get('syncStatus')!=m.get('ssot',{}).get('status'): blockers.append('COURSE_RELEASE_SSOT_MISMATCH')
        for e in m.get('manualEvidence',[]):
            expected=manual_gate_subject(course,e.get('gate'))
            if expected and e.get('subjectSha256')!=expected: blockers.append('MANUAL_EVIDENCE_STALE:'+e.get('gate','unknown'))
    else: blockers.append('COURSE_CONTRACT_MISSING')
    blockers=sorted(set(blockers))
    if require_approved and blockers: raise QAError('release blocked: '+', '.join(blockers))
    return m,blockers

def budget_guard():
    policy=load_jsonish(ROOT/'config/budget-policy.json'); issues=[]
    if policy.get('monthlyIncrementalBudgetUsd')!=0: issues.append('monthlyIncrementalBudgetUsd must remain 0')
    for k in ('allowLargerRunners','allowWorkersPaid','allowCloudflareContainers','allowPaidSaas'):
        if policy.get(k) is not False: issues.append(f'{k} must be false')
    allowed={'ubuntu-latest','windows-latest','macos-latest'}
    for wf in sorted((ROOT/'.github/workflows').glob('*.yml')):
        text=wf.read_text(encoding='utf-8')
        for runner in re.findall(r'(?m)^\s*runs-on:\s*([^#\n]+)',text):
            r=runner.strip().strip('"\'')
            if '${{' in r: issues.append(f'{wf.relative_to(ROOT)}: dynamic runs-on is not allowed in zero-cost baseline')
            elif r not in allowed: issues.append(f'{wf.relative_to(ROOT)}: disallowed/non-standard runner {r}')
        if 'pull_request_target:' in text: issues.append(f'{wf.relative_to(ROOT)}: pull_request_target forbidden')
    cfg=load_jsonish(ROOT/'wrangler.jsonc')
    if cfg.get('assets',{}).get('run_worker_first')!=['/api/*']: issues.append('wrangler assets.run_worker_first must be exactly ["/api/*"]')
    if 'containers' in cfg: issues.append('Cloudflare Containers configuration forbidden in zero-cost baseline')
    return {'status':'PASS' if not issues else 'FAIL','issues':issues,'policy':policy}

def deterministic_zip(input_dir:Path,out_path:Path):
    files=sorted([p for p in input_dir.rglob('*') if p.is_file()],key=lambda p:p.relative_to(input_dir).as_posix()); out_path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files:
            rel=p.relative_to(input_dir).as_posix(); info=zipfile.ZipInfo(rel,date_time=(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=(0o100644<<16); info.create_system=3; z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return sha256(out_path)
