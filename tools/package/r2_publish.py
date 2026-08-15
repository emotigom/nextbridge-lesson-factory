#!/usr/bin/env python3
"""Guarded R2 release publisher.

Default is dry-run. It never creates buckets, domains, DNS, plans, or credentials.
Actual writes require all of:
- an APPROVED/FIELD_READY+ manifest that passes lessonctl release policy,
- --execute,
- RELEASE_APPROVED=1,
- R2_RELEASE_BUCKET,
- CLOUDFLARE_ACCOUNT_ID,
- CLOUDFLARE_API_TOKEN.

Each immutable object is uploaded, downloaded again, and SHA/size verified before
latest.json is updated. A failed verification exits non-zero and leaves latest.json
unchanged.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/lessonctl'))
import lessonctl as lc

class PublishError(RuntimeError): pass

def sh(cmd, *, capture=False):
    cp=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=capture)
    if cp.returncode: raise PublishError((cp.stderr or '')+(cp.stdout or ''))
    return cp.stdout if capture else ''

def file_sha(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def wrangler_base(): return ['npx','--yes','wrangler@4.34.0','r2','object']

def build_plan(manifest_path:Path, root:Path, bucket:str):
    manifest, blockers=lc.verify_manifest(manifest_path,root,require_approved=True)
    if blockers: raise PublishError('unexpected release blockers: '+', '.join(blockers))
    plan=[]
    for a in manifest['assets']:
        key=lc.r2_key(manifest['courseId'],manifest['version'],a['sha256'],a['file'])
        plan.append({'file':a['file'],'sha256':a['sha256'],'size':a['size'],'mediaType':a['mediaType'],'key':key,'remote':f'{bucket}/{key}'})
    latest={'schemaVersion':'1.0.0','courseId':manifest['courseId'],'version':manifest['version'],'releaseDecision':'APPROVED','manifest':manifest_path.name,'assets':[{'file':x['file'],'sha256':x['sha256'],'key':x['key']} for x in plan]}
    return manifest,plan,latest

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',required=True); ap.add_argument('--root',required=True); ap.add_argument('--bucket',default=os.getenv('R2_RELEASE_BUCKET','UNCONFIGURED_RELEASE_BUCKET')); ap.add_argument('--execute',action='store_true'); args=ap.parse_args(); manifest_path=Path(args.manifest); root=Path(args.root)
    try:
        manifest,plan,latest=build_plan(manifest_path,root,args.bucket)
        if not args.execute:
            print(json.dumps({'status':'DRY_RUN_PASS','writesAttempted':False,'courseId':manifest['courseId'],'objects':plan,'latestKey':manifest['r2']['latestKey']},ensure_ascii=False,indent=2)); return
        if os.getenv('RELEASE_APPROVED')!='1': raise PublishError('RELEASE_APPROVED=1 is required for --execute')
        for name in ('R2_RELEASE_BUCKET','CLOUDFLARE_ACCOUNT_ID','CLOUDFLARE_API_TOKEN'):
            if not os.getenv(name): raise PublishError(f'missing required environment variable: {name}')
        if args.bucket!=os.environ['R2_RELEASE_BUCKET']: raise PublishError('--bucket must equal R2_RELEASE_BUCKET during execute')
        if shutil.which('npx') is None: raise PublishError('npx not found')
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            for i,x in enumerate(plan):
                src=root/x['file']; dl=td/f'object-{i}'; sh(wrangler_base()+['put',x['remote'],'--file',str(src),'--content-type',x['mediaType'],'--remote']); sh(wrangler_base()+['get',x['remote'],'--file',str(dl),'--remote'])
                if not dl.is_file() or dl.stat().st_size!=x['size'] or file_sha(dl)!=x['sha256']: raise PublishError('R2 re-download verification failed: '+x['file'])
            latest_path=td/'latest.json'; latest_path.write_text(json.dumps(latest,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8'); latest_remote=f"{args.bucket}/{manifest['r2']['latestKey']}"; sh(wrangler_base()+['put',latest_remote,'--file',str(latest_path),'--content-type','application/json','--remote'])
        print(json.dumps({'status':'PUBLISHED_VERIFIED','writesAttempted':True,'courseId':manifest['courseId'],'objectCount':len(plan),'latestKey':manifest['r2']['latestKey']},ensure_ascii=False,indent=2))
    except (lc.QAError,PublishError) as e:
        print(json.dumps({'status':'FAIL','error':str(e)},ensure_ascii=False,indent=2),file=sys.stderr); raise SystemExit(2)
if __name__=='__main__': main()
