#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, unicodedata, zipfile
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
STAGES=['DRAFT','CONTENT_QA','TECH_QA','INSTRUCTOR_PILOT','FIELD_PILOT','FIELD_READY','CANONICAL']
SHA_RE=re.compile(r'^[0-9a-f]{64}$')
NOTE_SECTIONS=['[주제]','[역할]','[선행 상태]','[선생님 대본]','[학생 절차]','[시간]','[산출물]','[성공 기준]','[복구]','[전환]']

class QAError(RuntimeError): pass

def load_jsonish(path:Path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha256(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def check_schema_subset(data,schema,path='$'):
    errs=[]
    def walk(v,s,p):
        typ=s.get('type'); types=typ if isinstance(typ,list) else ([typ] if typ else [])
        def ok(t): return {'object':isinstance(v,dict),'array':isinstance(v,list),'string':isinstance(v,str),'integer':isinstance(v,int) and not isinstance(v,bool),'number':isinstance(v,(int,float)) and not isinstance(v,bool),'boolean':isinstance(v,bool),'null':v is None}.get(t,True)
        if types and not any(ok(t) for t in types): errs.append(f'{p}: type expected {types}'); return
        if 'const' in s and v!=s['const']: errs.append(f'{p}: const mismatch')
        if 'enum' in s and v not in s['enum']: errs.append(f'{p}: not in enum')
        if isinstance(v,str):
            if 'minLength' in s and len(v)<s['minLength']: errs.append(f'{p}: too short')
            if 'pattern' in s and not re.search(s['pattern'],v): errs.append(f'{p}: pattern mismatch')
        if isinstance(v,(int,float)) and not isinstance(v,bool):
            if 'minimum' in s and v<s['minimum']: errs.append(f'{p}: below minimum')
            if 'maximum' in s and v>s['maximum']: errs.append(f'{p}: above maximum')
        if isinstance(v,dict):
            for k in s.get('required',[]):
                if k not in v: errs.append(f'{p}: missing {k}')
            props=s.get('properties',{})
            if s.get('additionalProperties') is False:
                for k in v:
                    if k not in props: errs.append(f'{p}: unexpected {k}')
            for k,sv in props.items():
                if k in v: walk(v[k],sv,f'{p}.{k}')
        if isinstance(v,list):
            if 'minItems' in s and len(v)<s['minItems']: errs.append(f'{p}: too few items')
            if 'items' in s:
                for i,x in enumerate(v): walk(x,s['items'],f'{p}[{i}]')
    walk(data,schema,path); return errs

def course_path(course_id): return ROOT/'courses'/course_id/'course.yaml'
def validate_course(course): return check_schema_subset(course,load_jsonish(ROOT/'contracts/course.schema.json'))

def wip_check(current):
    active=[]
    for p in sorted((ROOT/'courses').glob('*/course.yaml')):
        try: c=load_jsonish(p)
        except Exception as e: raise QAError(f'course parse failed {p}: {e}')
        if c.get('activeWip'): active.append((p,c))
    if len(active)!=1: return False,f'active WIP count={len(active)}; expected 1'
    if active[0][1].get('courseId')!=current.get('courseId'): return False,'requested course is not active WIP'
    return True,'exactly one active WIP'

def golden_check(course):
    g=load_jsonish(ROOT/course['goldenFixture']); e=g['expected']; s=course['sourceLock']
    pairs={'packageSha256':'packageSha256','runtimeHtmlSha256':'runtimeHtmlSha256','stateRunnerSha256':'stateRunnerSha256','runtimeQaSha256':'runtimeQaSha256','prototypePptxSha256':'prototypePptxSha256'}
    bad=[k for k,v in pairs.items() if e[k]!=s[v]]
    return (not bad,'frozen hashes match golden contract' if not bad else 'golden mismatch: '+','.join(bad),g)

def scan_public_safety():
    forbidden_ext={'.pptx','.ppt','.docx','.hwpx','.mp4','.mov','.ttf','.otf'}; bad=[]; pii=[]; secret_like=[]
    text_ext={'.md','.json','.yaml','.yml','.py','.js','.mjs','.html','.css','.txt','.sh','.jsonc'}
    for p in ROOT.rglob('*'):
        if not p.is_file() or '.git' in p.parts or 'out' in p.parts or '__pycache__' in p.parts: continue
        rel=p.relative_to(ROOT).as_posix()
        if p.suffix.lower() in forbidden_ext: bad.append(rel)
        if p.suffix.lower()=='.zip' and not rel.startswith('tests/'): bad.append(rel)
        if p.suffix.lower() in text_ext or p.name=='lessonctl':
            text=p.read_text(encoding='utf-8',errors='replace')
            if re.search(r'\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b',text): pii.append(rel+':phone-like')
            if re.search(r'\b\d{6}[- ]?[1-4]\d{6}\b',text): pii.append(rel+':rrn-like')
            for pat,name in [(r'ghp_[A-Za-z0-9]{20,}','github-token'),(r'github_pat_[A-Za-z0-9_]{20,}','github-pat'),(r'sk-[A-Za-z0-9]{20,}','api-key')]:
                if re.search(pat,text): secret_like.append(rel+':'+name)
    issues=bad+pii+secret_like
    return (not issues,'no restricted binary/PII/secret-like literal committed' if not issues else 'public safety findings: '+','.join(issues))

def html_qa(path:Path):
    text=path.read_text(encoding='utf-8',errors='replace'); external=re.findall(r"(?:src|href)=[\"'](https?://[^\"']+)[\"']",text,re.I); apis=[x for x in ['fetch(','XMLHttpRequest','WebSocket(','EventSource('] if x in text]; pii=[]
    if re.search(r'\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b',text): pii.append('phone-like')
    if re.search(r'\b\d{6}[- ]?[1-4]\d{6}\b',text): pii.append('rrn-like')
    return {'externalRefs':sorted(set(external)),'networkApis':apis,'piiPatterns':pii,'pass':not external and not apis and not pii}

def _zip_norm(base:PurePosixPath,target:str):
    target=target.replace('\\','/'); p=PurePosixPath(target.lstrip('/')) if target.startswith('/') else (base/PurePosixPath(target)); out=[]
    for part in p.parts:
        if part in ('','.'): continue
        if part=='..':
            if out: out.pop()
        else: out.append(part)
    return PurePosixPath(*out).as_posix()
