#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core import ROOT, QAError, NOTE_SECTIONS, load_jsonish, course_path, validate_course, wip_check, golden_check, scan_public_safety, html_qa
from private_replay import verify_private_package
from release_policy import verify_manifest, budget_guard, deterministic_zip, r2_key, release_policy, manual_gate_subject
from pptx_checks import pptx_qa
from evidence import evidence_subject, stage_check, verify_evidence
from dashboard import build_dashboard, verify_dashboard

def qa(course_id,mode,private_package=None):
    cp=course_path(course_id); course=load_jsonish(cp); checks=[]; failures=[]; blockers=[]
    errs=validate_course(course); checks.append({'name':'course_schema','status':'PASS' if not errs else 'FAIL','detail':errs or 'valid'}); failures+=errs
    ok,detail=wip_check(course); checks.append({'name':'wip_one','status':'PASS' if ok else 'FAIL','detail':detail});
    if not ok: failures.append(detail)
    ok,detail,g=golden_check(course); checks.append({'name':'golden_contract','status':'PASS' if ok else 'FAIL','detail':detail});
    if not ok: failures.append(detail)
    ok,detail=scan_public_safety(); checks.append({'name':'public_repo_safety','status':'PASS' if ok else 'FAIL','detail':detail});
    if not ok: failures.append(detail)
    ok,detail=verify_dashboard(course); checks.append({'name':'dashboard_contract','status':'PASS' if ok else 'FAIL','detail':detail});
    if not ok: failures.append(detail)
    if course['ssot']['syncStatus']!='SYNCED': blockers.append('SSOT_'+course['ssot']['syncStatus'])
    if course['quality']['status']!='SCORED' or course['quality']['overall'] is None: blockers.append('QUALITY_NOT_SCORED')
    if course['rights']['status']!='VERIFIED': blockers.append('RIGHTS_UNVERIFIED')
    pending=[g['id'] for g in course['manualGates'] if g['status']!='PASS']
    if pending: blockers.append('MANUAL_GATES_PENDING')
    private=None
    if private_package:
        try:
            private=verify_private_package(course,Path(private_package)); checks.append({'name':'private_golden_replay','status':'PASS','detail':'actual v0.4 package replayed'})
        except Exception as e:
            failures.append(str(e)); checks.append({'name':'private_golden_replay','status':'FAIL','detail':str(e)})
    elif mode=='full':
        checks.append({'name':'private_golden_replay','status':'SKIPPED_POLICY','detail':'actual rights-unverified binary is intentionally absent from public Git; run locally/private CI with --private-package'})
        blockers.append('PRIVATE_SOURCE_REPLAY_NOT_RUN_IN_PUBLIC_CI')
    return {'schemaVersion':'1.0.0','courseId':course_id,'mode':mode,'status':'FAIL' if failures else 'PASS','releaseDecision':course['releaseDecision'],'stage':course['stage'],'subject':course['sourceLock'],'checks':checks,'promotionBlockers':sorted(set(blockers)),'manualGates':course['manualGates'],'privateReplay':private,'failures':failures}

def impact(base,head):
    cp=subprocess.run(['git','diff','--name-only',base,head],cwd=ROOT,text=True,capture_output=True)
    if cp.returncode: raise QAError(cp.stderr.strip() or 'git diff failed')
    changed=[x for x in cp.stdout.splitlines() if x.strip()]; full=any(x.startswith(('contracts/','tools/','fixtures/golden/','.github/workflows/')) or x.endswith(('.pptx','.html','.js','.mjs')) for x in changed)
    return {'changed':changed,'recommended':'full' if full else 'fast'}

def main():
    p=argparse.ArgumentParser(prog='lessonctl'); sub=p.add_subparsers(dest='cmd',required=True)
    i=sub.add_parser('intake'); i.add_argument('path')
    q=sub.add_parser('qa'); q.add_argument('mode',choices=['fast','full']); q.add_argument('--course',required=True); q.add_argument('--json',dest='jsonout'); q.add_argument('--private-package')
    pkg=sub.add_parser('package'); pkgsub=pkg.add_subparsers(dest='pkgcmd',required=True); cand=pkgsub.add_parser('candidate'); cand.add_argument('--input-dir',required=True); cand.add_argument('--out',required=True); cand.add_argument('--course',required=True)
    r=sub.add_parser('release'); rsub=r.add_subparsers(dest='relcmd',required=True); v=rsub.add_parser('verify'); v.add_argument('--manifest',required=True); v.add_argument('--root'); v.add_argument('--require-approved',action='store_true')
    im=sub.add_parser('impact'); im.add_argument('--base',required=True); im.add_argument('--head',required=True)
    b=sub.add_parser('budget'); bsub=b.add_subparsers(dest='budgetcmd',required=True); bsub.add_parser('check')
    ev=sub.add_parser('evidence'); evsub=ev.add_subparsers(dest='evcmd',required=True); evv=evsub.add_parser('verify'); evv.add_argument('--course',required=True); evv.add_argument('--file',required=True); evs=evsub.add_parser('subject'); evs.add_argument('--course',required=True); evs.add_argument('--gate',required=True)
    st=sub.add_parser('stage'); stsub=st.add_subparsers(dest='stagecmd',required=True); stc=stsub.add_parser('check'); stc.add_argument('--course',required=True); stc.add_argument('--to',required=True); stc.add_argument('--evidence-dir')
    db=sub.add_parser('dashboard'); dbsub=db.add_subparsers(dest='dbcmd',required=True); dbb=dbsub.add_parser('build'); dbb.add_argument('--course',required=True); dbb.add_argument('--out-dir',default='apps/dashboard/data'); dbv=dbsub.add_parser('verify'); dbv.add_argument('--course',required=True); dbv.add_argument('--out-dir',default='apps/dashboard/data')
    a=p.parse_args()
    try:
        if a.cmd=='intake':
            c=load_jsonish(Path(a.path)); errs=validate_course(c); ok,detail=wip_check(c); errs += [] if ok else [detail]
            print(json.dumps({'status':'PASS' if not errs else 'FAIL','errors':errs},ensure_ascii=False,indent=2)); sys.exit(1 if errs else 0)
        if a.cmd=='qa':
            rep=qa(a.course,a.mode,a.private_package); txt=json.dumps(rep,ensure_ascii=False,indent=2)+'\n'
            if a.jsonout:
                out=Path(a.jsonout); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(txt,encoding='utf-8')
            print(txt,end=''); sys.exit(1 if rep['status']=='FAIL' else 0)
        if a.cmd=='package':
            c=load_jsonish(course_path(a.course)); out=Path(a.out); s1=deterministic_zip(Path(a.input_dir),out)
            with tempfile.TemporaryDirectory() as td:
                second=Path(td)/'second.zip'; s2=deterministic_zip(Path(a.input_dir),second)
            if s1!=s2: raise QAError('deterministic package mismatch')
            print(json.dumps({'status':'INTEGRITY_PASS','releaseDecision':c['releaseDecision'],'zipSha256':s1,'deterministic':True},indent=2)); return
        if a.cmd=='release':
            m,b=verify_manifest(Path(a.manifest),Path(a.root) if a.root else None,a.require_approved); print(json.dumps({'status':'RELEASE_APPROVED' if not b else 'HOLD','blockers':b,'courseId':m['courseId']},ensure_ascii=False,indent=2)); return
        if a.cmd=='budget':
            rep=budget_guard(); print(json.dumps(rep,ensure_ascii=False,indent=2)); sys.exit(1 if rep['status']=='FAIL' else 0)
        if a.cmd=='evidence':
            if a.evcmd=='subject':
                print(json.dumps({'courseId':a.course,'gate':a.gate,'subjectSha256':evidence_subject(a.course,a.gate)},ensure_ascii=False,indent=2)); return
            course=load_jsonish(course_path(a.course)); evidence=load_jsonish(Path(a.file)); ok,blockers=verify_evidence(course,evidence)
            print(json.dumps({'status':'PASS' if ok else 'FAIL','blockers':blockers,'gate':evidence.get('gate')},ensure_ascii=False,indent=2)); sys.exit(0 if ok else 2)
        if a.cmd=='stage':
            course=load_jsonish(course_path(a.course)); blockers=stage_check(course,a.to,Path(a.evidence_dir) if a.evidence_dir else None)
            print(json.dumps({'status':'PASS' if not blockers else 'HOLD','courseId':a.course,'from':course.get('stage'),'to':a.to,'blockers':blockers},ensure_ascii=False,indent=2)); sys.exit(0 if not blockers else 2)
        if a.cmd=='dashboard':
            course=load_jsonish(course_path(a.course)); out=ROOT/Path(a.out_dir)
            if a.dbcmd=='build': build_dashboard(course,out); print(json.dumps({'status':'BUILT','courseId':a.course,'outDir':str(out.relative_to(ROOT))},ensure_ascii=False,indent=2)); return
            ok,detail=verify_dashboard(course,out); print(json.dumps({'status':'PASS' if ok else 'FAIL','detail':detail},ensure_ascii=False,indent=2)); sys.exit(0 if ok else 2)
        if a.cmd=='impact': print(json.dumps(impact(a.base,a.head),ensure_ascii=False,indent=2)); return
    except QAError as e:
        print(json.dumps({'status':'FAIL','error':str(e)},ensure_ascii=False,indent=2),file=sys.stderr); sys.exit(2)

if __name__=='__main__': main()
