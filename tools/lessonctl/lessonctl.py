#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core import ROOT, QAError, NOTE_SECTIONS, load_jsonish, course_path, validate_course, wip_check, golden_check, scan_public_safety, html_qa
from private_replay import verify_private_package
from release_policy import verify_manifest, budget_guard, deterministic_zip, r2_key, release_policy, manual_gate_subject
from pptx_checks import pptx_qa

def qa(course_id,mode,private_package=None):
    course=load_jsonish(course_path(course_id)); checks=[]; failures=[]; blockers=[]
    errs=validate_course(course); checks.append({'name':'course_schema','status':'PASS' if not errs else 'FAIL','detail':errs or 'valid'}); failures+=errs
    ok,detail=wip_check(course); checks.append({'name':'wip_one','status':'PASS' if ok else 'FAIL','detail':detail}); failures += [] if ok else [detail]
    ok,detail,g=golden_check(course); checks.append({'name':'golden_contract','status':'PASS' if ok else 'FAIL','detail':detail}); failures += [] if ok else [detail]
    ok,detail=scan_public_safety(); checks.append({'name':'public_repo_safety','status':'PASS' if ok else 'FAIL','detail':detail}); failures += [] if ok else [detail]
    if course['ssot']['syncStatus']!='SYNCED': blockers.append('SSOT_'+course['ssot']['syncStatus'])
    if course['quality']['status']!='SCORED' or course['quality']['overall'] is None: blockers.append('QUALITY_NOT_SCORED')
    if course['rights']['status']!='VERIFIED': blockers.append('RIGHTS_UNVERIFIED')
    if any(g['status']!='PASS' for g in course['manualGates']): blockers.append('MANUAL_GATES_PENDING')
    private=None
    if private_package:
        try: private=verify_private_package(course,Path(private_package)); checks.append({'name':'private_golden_replay','status':'PASS','detail':'actual v0.4 package replayed'})
        except Exception as e: failures.append(str(e)); checks.append({'name':'private_golden_replay','status':'FAIL','detail':str(e)})
    elif mode=='full': checks.append({'name':'private_golden_replay','status':'SKIPPED_POLICY','detail':'actual rights-unverified binary is intentionally absent from public Git; run locally/private CI with --private-package'}); blockers.append('PRIVATE_SOURCE_REPLAY_NOT_RUN_IN_PUBLIC_CI')
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
    a=p.parse_args()
    try:
        if a.cmd=='intake':
            c=load_jsonish(Path(a.path)); errs=validate_course(c); ok,detail=wip_check(c); errs += [] if ok else [detail]; print(json.dumps({'status':'PASS' if not errs else 'FAIL','errors':errs},ensure_ascii=False,indent=2)); sys.exit(1 if errs else 0)
        if a.cmd=='qa':
            rep=qa(a.course,a.mode,a.private_package); txt=json.dumps(rep,ensure_ascii=False,indent=2)+'\n'
            if a.jsonout: out=Path(a.jsonout); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(txt,encoding='utf-8')
            print(txt,end=''); sys.exit(1 if rep['status']=='FAIL' else 0)
        if a.cmd=='package':
            c=load_jsonish(course_path(a.course)); out=Path(a.out); s1=deterministic_zip(Path(a.input_dir),out)
            with tempfile.TemporaryDirectory() as td: s2=deterministic_zip(Path(a.input_dir),Path(td)/'second.zip')
            if s1!=s2: raise QAError('deterministic package mismatch')
            print(json.dumps({'status':'INTEGRITY_PASS','releaseDecision':c['releaseDecision'],'zipSha256':s1,'deterministic':True},indent=2)); return
        if a.cmd=='release':
            m,b=verify_manifest(Path(a.manifest),Path(a.root) if a.root else None,a.require_approved); print(json.dumps({'status':'RELEASE_APPROVED' if not b else 'HOLD','blockers':b,'courseId':m['courseId']},ensure_ascii=False,indent=2)); return
        if a.cmd=='budget': rep=budget_guard(); print(json.dumps(rep,ensure_ascii=False,indent=2)); sys.exit(1 if rep['status']=='FAIL' else 0)
        if a.cmd=='impact': print(json.dumps(impact(a.base,a.head),ensure_ascii=False,indent=2)); return
    except QAError as e: print(json.dumps({'status':'FAIL','error':str(e)},ensure_ascii=False,indent=2),file=sys.stderr); sys.exit(2)

if __name__=='__main__': main()
