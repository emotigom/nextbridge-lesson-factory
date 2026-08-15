from __future__ import annotations
import re, zipfile
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET
from core import NOTE_SECTIONS, _zip_norm

def pptx_qa(path:Path):
    issues=[]; warn=[]; result={}
    with zipfile.ZipFile(path) as z:
        names=z.namelist(); name_set=set(names)
        if z.testzip(): issues.append('CRC failure')
        for n in names:
            pp=PurePosixPath(n)
            if pp.is_absolute() or '..' in pp.parts: issues.append(f'unsafe path:{n}')
        try: ET.fromstring(z.read('[Content_Types].xml'))
        except Exception as e: issues.append('Content_Types parse:'+str(e))
        roots={}
        for n in [x for x in names if x.endswith(('.xml','.rels'))]:
            try: roots[n]=ET.fromstring(z.read(n))
            except Exception as e: issues.append(f'xml parse {n}:{e}')
        for n in [x for x in names if x.lower().endswith('.svg')]:
            try: ET.fromstring(z.read(n))
            except Exception as e: issues.append(f'svg parse {n}:{e}')
        external_relationships=[]
        for n,r in roots.items():
            if not n.endswith('.rels'): continue
            base=PurePosixPath(n).parent.parent
            for rel in list(r):
                t=rel.attrib.get('Target','')
                if rel.attrib.get('TargetMode')=='External': external_relationships.append({'rels':n,'target':t,'type':rel.attrib.get('Type','')}); continue
                resolved=_zip_norm(base,t)
                if resolved and resolved not in name_set: issues.append(f'missing relationship target:{n}->{t}')
        slides=sorted([n for n in names if re.match(r'ppt/slides/slide\d+\.xml$',n)]); notes=sorted([n for n in names if re.match(r'ppt/notesSlides/notesSlide\d+\.xml$',n)])
        result['slides']=len(slides); result['notes']=len(notes); result['hiddenSlides']=sum(1 for n in slides if roots.get(n) is not None and roots[n].attrib.get('show')=='0')
        referenced=set(); pres=roots.get('ppt/presentation.xml'); presrels=roots.get('ppt/_rels/presentation.xml.rels')
        if pres is not None and presrels is not None:
            rid_to_target={r.attrib.get('Id'):r.attrib.get('Target') for r in list(presrels)}; nsr='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
            for node in pres.iter():
                rid=node.attrib.get(nsr)
                if rid in rid_to_target and 'slides/' in rid_to_target[rid]: referenced.add(_zip_norm(PurePosixPath('ppt'),rid_to_target[rid]))
        result['orphanSlides']=sorted(set(slides)-referenced) if referenced else []
        placeholder_text=[]; fonts=set(); languages=set(); exponent=[]; bad_shadow=[]; note_sections_missing=[]; empty_notes=[]; out_of_bounds=[]; slide_cx=slide_cy=None
        if pres is not None:
            for el in pres.iter():
                if el.tag.rsplit('}',1)[-1]=='sldSz':
                    try: slide_cx=int(el.attrib.get('cx','0')); slide_cy=int(el.attrib.get('cy','0'))
                    except ValueError: pass
        for n,r in roots.items():
            for el in r.iter():
                tag=el.tag.rsplit('}',1)[-1]
                if tag=='t' and el.text and re.search(r'click to add|텍스트를 입력|제목을 입력',el.text,re.I): placeholder_text.append((n,el.text[:80]))
                if tag in ('latin','ea','cs') and el.attrib.get('typeface'): fonts.add(el.attrib['typeface'])
                if el.attrib.get('lang'): languages.add(el.attrib['lang'])
                for k,v in el.attrib.items():
                    if re.fullmatch(r'[-+]?\d+(?:\.\d+)?[eE][+-]?\d+',v): exponent.append((n,k,v))
                if tag in ('outerShdw','innerShdw'):
                    for k in ('blurRad','dist','dir'):
                        v=el.attrib.get(k)
                        if v and (not re.fullmatch(r'-?\d+',v) or abs(int(v))>500000000): bad_shadow.append((n,k,v))
        if slide_cx and slide_cy:
            for n in slides:
                r=roots.get(n)
                if r is None: continue
                for xfrm in [e for e in r.iter() if e.tag.rsplit('}',1)[-1]=='xfrm']:
                    off=next((e for e in list(xfrm) if e.tag.rsplit('}',1)[-1]=='off'),None); ext=next((e for e in list(xfrm) if e.tag.rsplit('}',1)[-1]=='ext'),None)
                    if off is None or ext is None: continue
                    try: x=int(off.attrib.get('x','0')); y=int(off.attrib.get('y','0')); cx=int(ext.attrib.get('cx','0')); cy=int(ext.attrib.get('cy','0'))
                    except ValueError: continue
                    if x<0 or y<0 or cx<0 or cy<0 or x+cx>slide_cx or y+cy>slide_cy: out_of_bounds.append({'slide':n,'x':x,'y':y,'cx':cx,'cy':cy})
        for n in notes:
            r=roots.get(n); texts=[] if r is None else [(e.text or '') for e in r.iter() if e.tag.endswith('}t')]; txt='\n'.join(texts).strip()
            if not txt: empty_notes.append(n); continue
            miss=[s for s in NOTE_SECTIONS if s not in txt]
            if miss: note_sections_missing.append({'note':n,'missing':miss})
        result.update({'placeholderText':placeholder_text,'fonts':sorted(fonts),'languages':sorted(languages),'embeddedFontParts':len([n for n in names if n.startswith('ppt/fonts/')]),'externalRelationships':external_relationships,'outOfBoundsShapeCandidates':out_of_bounds,'drawingExponentAttributes':exponent,'abnormalShadows':bad_shadow,'emptyNotes':empty_notes,'noteSectionsMissing':note_sections_missing})
        if placeholder_text: issues.append('visible placeholder text')
        if exponent: issues.append('DrawingML exponent notation')
        if bad_shadow: issues.append('abnormal shadow numeric value')
        if empty_notes: issues.append('empty speaker notes')
        if note_sections_missing: issues.append('required note sections missing')
        if len(notes)<len(slides): issues.append('notes count < slide count')
        if result['orphanSlides']: issues.append('orphan slides')
        if result['embeddedFontParts']==0 and result['fonts']: warn.append('fonts referenced but not embedded')
        if not result['languages']: warn.append('no explicit language tags found in parsed PPTX XML')
    result['issues']=issues; result['warnings']=warn; result['pass']=not issues
    return result
