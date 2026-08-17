import sys, tempfile, unittest, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/lessonctl'))
from core import load_jsonish
from presentation_template import presentation_template_qa

POLICY=load_jsonish(ROOT/'policies/presentation-templates/2026-visiting-ai.json')


def custom_xml(template_id='2026-visiting-ai'):
    props=POLICY['candidatePptxCustomProperties'].copy()
    props['NextbridgeTemplateId']=template_id
    body=[]
    for pid,(name,value) in enumerate(props.items(),2):
        body.append(f'<property fmtid="{{D5CDD505-2E9C-101B-9397-08002B2CF9AE}}" pid="{pid}" name="{name}"><vt:lpwstr>{value}</vt:lpwstr></property>')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'+''.join(body)+'</Properties>'


def slide_xml(text):
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'


def rels_xml(kind,target):
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{kind}" Target="{target}"/></Relationships>'


def build_pptx(path: Path, template_id='2026-visiting-ai', cover_ok=True):
    fp=POLICY['structuralFingerprint']
    layout_names=fp['layoutNames']
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('ppt/presentation.xml',f'<?xml version="1.0" encoding="UTF-8"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldSz cx="{fp["slideWidthEmu"]}" cy="{fp["slideHeightEmu"]}"/></p:presentation>')
        z.writestr('docProps/custom.xml',custom_xml(template_id))
        z.writestr('ppt/slideMasters/slideMaster1.xml','<?xml version="1.0" encoding="UTF-8"?><p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>')
        for i,name in enumerate(layout_names,1):
            z.writestr(f'ppt/slideLayouts/slideLayout{i}.xml',f'<?xml version="1.0" encoding="UTF-8"?><p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld name="{name}"/></p:sldLayout>')
            z.writestr(f'ppt/slideLayouts/_rels/slideLayout{i}.xml.rels',rels_xml('slideMaster','../slideMasters/slideMaster1.xml'))
        cover='2026년 찾아가는 AI교육 지원 프로그램 운영' if cover_ok else '다른 표지'
        closing='2026년 찾아가는 AI교실 교육 프로그램 감사합니다.'
        z.writestr('ppt/slides/slide1.xml',slide_xml(cover))
        z.writestr('ppt/slides/slide2.xml',slide_xml(closing))
        for i in (1,2):
            z.writestr(f'ppt/slides/_rels/slide{i}.xml.rels',rels_xml('slideLayout','../slideLayouts/slideLayout1.xml'))


class TestPresentationTemplate(unittest.TestCase):
    def test_matching_template_passes(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ok.pptx'; build_pptx(p)
            report=presentation_template_qa(p,POLICY)
            self.assertTrue(report['pass'],report['issues'])

    def test_wrong_template_id_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.pptx'; build_pptx(p,template_id='wrong-template')
            report=presentation_template_qa(p,POLICY)
            self.assertFalse(report['pass'])
            self.assertIn('TEMPLATE_CUSTOM_PROPERTY_MISMATCH:NextbridgeTemplateId',report['issues'])

    def test_missing_required_cover_text_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.pptx'; build_pptx(p,cover_ok=False)
            report=presentation_template_qa(p,POLICY)
            self.assertFalse(report['pass'])
            self.assertTrue(any(x.startswith('TEMPLATE_COVER_TEXT_MISSING:') for x in report['issues']))

if __name__=='__main__': unittest.main()
