from __future__ import annotations
import os, subprocess, tempfile, unicodedata, zipfile
from pathlib import Path, PurePosixPath
from core import ROOT, QAError, load_jsonish, sha256, html_qa
from pptx_checks import pptx_qa
from presentation_template import load_template_policy, presentation_template_qa
from package_checks import verify_inventory, html_runtime_contract, runtime_report_contract, manifest_contract


def verify_private_package(course,zip_path:Path):
    out={'provided':True,'packageSha256':sha256(zip_path),'checks':[]}
    if out['packageSha256']!=course['sourceLock']['packageSha256']: raise QAError('private package SHA mismatch')
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        with zipfile.ZipFile(zip_path) as z:
            if z.testzip(): raise QAError('package ZIP CRC failure')
            names=z.namelist()
            if len(names)!=len(set(names)): raise QAError('duplicate ZIP path')
            normalized=[unicodedata.normalize('NFC',n) for n in names]
            if len(normalized)!=len(set(normalized)): raise QAError('Unicode-normalization ZIP path collision')
            for n in names:
                pp=PurePosixPath(n)
                if pp.is_absolute() or '..' in pp.parts: raise QAError('unsafe ZIP path')
                if any(part.startswith('.') for part in pp.parts if part not in ('','.')): raise QAError('hidden ZIP path forbidden: '+n)
            z.extractall(td)
        dirs=[p for p in td.iterdir() if p.is_dir()]
        base=dirs[0] if len(dirs)==1 else td
        manifests=sorted(base.glob('release_manifest*.json'))
        if not manifests: raise QAError('release manifest missing')
        manifest_path=manifests[0]; manifest=load_jsonish(manifest_path); assets=manifest.get('assets',[])
        checksum_files=sorted(base.glob('CHECKSUMS_SHA256*.txt'))
        if len(checksum_files)!=1: raise QAError('exactly one checksum file required')
        inventory=verify_inventory(base,manifest_path,checksum_files[0])
        out['checks'].append({'name':'manifest_assets','status':'PASS',**inventory})
        golden=load_jsonish(ROOT/course['goldenFixture'])
        expected=golden.get('expected',{})
        prototype_expected=expected.get('prototype',{})
        expected_slides=int(prototype_expected.get('slides',0) or 0)
        expected_notes=int(prototype_expected.get('notes',0) or 0)
        if expected_slides < 1 or expected_notes < 1:
            raise QAError('golden prototype slide/note expectation missing')
        contract=manifest_contract(manifest,golden,load_jsonish(ROOT/'config/budget-policy.json'))
        out['checks'].append({'name':'package_manifest_contract','status':'PASS',**contract})
        validators=sorted(base.glob('validate_package*.mjs'))
        if validators:
            cp=subprocess.run(['node',validators[0].name,'.'],cwd=base,text=True,capture_output=True)
            if cp.returncode: raise QAError('embedded validator failed: '+cp.stderr+cp.stdout)
            out['checks'].append({'name':'embedded_validator','status':'PASS','output':cp.stdout.strip()})
        html_asset=next((a for a in assets if a.get('role')=='student-runtime'),None)
        ppt_asset=next((a for a in assets if a.get('role')=='prototype-presentation'),None)
        ppt_qa_asset=next((a for a in assets if a.get('role')=='prototype-qa-report'),None)
        render_asset=next((a for a in assets if a.get('role')=='prototype-render-evidence'),None)
        preview_asset=next((a for a in assets if a.get('role')=='prototype-preview'),None)
        runner_asset=next((a for a in assets if a.get('role')=='runtime-test-runner'),None)
        report_asset=next((a for a in assets if a.get('role')=='runtime-qa-report'),None)
        if html_asset:
            hq=html_qa(base/html_asset['file']); out['html']=hq
            if not hq['pass']: raise QAError('HTML offline/privacy gate failed')
            hc=html_runtime_contract(base/html_asset['file'],manifest); out['htmlContract']=hc
            out['checks'].append({'name':'runtime_html_contract','status':'PASS','idCount':hc['idCount']})
        if ppt_asset:
            ppt_path=base/ppt_asset['file']
            pq=pptx_qa(ppt_path); out['pptx']=pq
            if not pq['pass']: raise QAError('PPTX structural gate failed')
            if pq['slides']!=expected_slides or pq['notes']!=expected_notes:
                raise QAError('golden prototype slide/note count mismatch')
            binding=course.get('presentationTemplate')
            if binding:
                policy,_=load_template_policy(binding.get('templateId'),binding.get('policyPath'))
                tq=presentation_template_qa(ppt_path,policy); out['presentationTemplate']=tq
                if not tq['pass']:
                    raise QAError('PPTX presentation template hard gate failed: ' + '; '.join(tq['issues']))
                out['checks'].append({'name':'presentation_template_hard_gate','status':'PASS','templateId':policy.get('templateId')})
        if ppt_asset and ppt_qa_asset:
            qj=load_jsonish(base/ppt_qa_asset['file'])
            if qj.get('sha256')!=ppt_asset['sha256'] or qj.get('slideCount')!=expected_slides or qj.get('passed') is not True or qj.get('failures'):
                raise QAError('prototype QA report cross-contract failed')
            if not qj.get('checks') or not all(v is True for v in qj['checks'].values()): raise QAError('prototype QA checks not all true')
            out['checks'].append({'name':'prototype_qa_cross_contract','status':'PASS','checkCount':len(qj['checks'])})
        if ppt_asset and render_asset:
            rj=load_jsonish(base/render_asset['file']); ge=prototype_expected
            ar=rj.get('artifactRender',{}); st=rj.get('slidesTest',{})
            pages=ar.get('pages',[])
            if rj.get('subjectSha256')!=ppt_asset['sha256']: raise QAError('render evidence subject SHA mismatch')
            if rj.get('baselineSha256')!=ge.get('baselinePptxSha256'): raise QAError('render evidence baseline SHA mismatch')
            if ar.get('pageCount')!=expected_slides or len(pages)!=expected_slides or not all(x.get('pixelEqual') is True for x in pages): raise QAError('pixel regression evidence failed')
            if st.get('status')!='PASS' or st.get('overflowCount')!=0: raise QAError('overflow evidence failed')
            if preview_asset and rj.get('preview',{}).get('sha256')!=preview_asset['sha256']: raise QAError('preview evidence SHA mismatch')
            out['checks'].append({'name':'prototype_render_evidence','status':'PASS','pixelEqualPages':len(pages),'overflow':0,'fontApproval':False})
        if html_asset and report_asset:
            rc=runtime_report_contract(base/report_asset['file'],html_asset,manifest,expected)
            out['checks'].append({'name':'runtime_report_contract','status':'PASS',**rc})
        if runner_asset and html_asset and report_asset:
            cp=subprocess.run(['node',runner_asset['file'],html_asset['file'],report_asset['file']],cwd=base,text=True,capture_output=True,env={**os.environ,'SOURCE_DATE_EPOCH':'0'})
            if cp.returncode: raise QAError('runtime state runner failed: '+cp.stderr+cp.stdout)
            actual=sha256(base/report_asset['file'])
            if actual!=course['sourceLock']['runtimeQaSha256']: raise QAError(f'deterministic runtime report mismatch: {actual}')
            out['checks'].append({'name':'runtime_state_transition','status':'PASS','output':cp.stdout.strip(),'reportSha256':actual})
    return out
