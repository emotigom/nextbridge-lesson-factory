import importlib.util, json, tempfile, unittest, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lessonctl',ROOT/'tools/lessonctl/lessonctl.py'); lc=importlib.util.module_from_spec(spec); spec.loader.exec_module(lc)

class TestLessonCtl(unittest.TestCase):
 def test_course_schema_and_wip(self):
  c=lc.load_jsonish(ROOT/'courses/feed-why/course.yaml'); self.assertEqual([],lc.validate_course(c)); self.assertTrue(lc.wip_check(c)[0])
 def test_golden_contract_locked(self):
  c=lc.load_jsonish(ROOT/'courses/feed-why/course.yaml'); ok,_,g=lc.golden_check(c); self.assertTrue(ok); self.assertEqual(34,g['expected']['runtimeChecks']['passed']); self.assertEqual(108,g['expected']['runtimeChecks']['supportedMatrixPassed']); self.assertEqual([4,5,10,20,27],g['expected']['prototype']['sourceSlides']); self.assertTrue(g['expected']['prototype']['visibleRenderPixelEqual'])
 def test_public_repo_has_no_actual_lesson_binary(self): self.assertTrue(lc.scan_public_safety()[0])
 def test_deterministic_zip(self):
  with tempfile.TemporaryDirectory() as td:
   td=Path(td); d=td/'in'; d.mkdir(); (d/'b.txt').write_text('B',encoding='utf-8'); (d/'a.txt').write_text('A',encoding='utf-8'); a=lc.deterministic_zip(d,td/'a.zip'); b=lc.deterministic_zip(d,td/'b.zip'); self.assertEqual(a,b)
 def test_release_hold_is_not_approved(self):
  m=json.loads((ROOT/'releases/manifests/feed-why-v0.4.example.json').read_text()); blockers=lc.release_policy(m); self.assertIn('RELEASE_DECISION_NOT_APPROVED',blockers); self.assertIn('STAGE_BELOW_FIELD_READY',blockers)
  with self.assertRaises(lc.QAError): lc.release_policy(m,True)
 def test_release_thresholds_cannot_be_bypassed(self):
  m=json.loads((ROOT/'releases/manifests/feed-why-v0.4.example.json').read_text())
  m['releaseDecision']='APPROVED'; m['stage']='FIELD_READY'; m['rights']={'status':'VERIFIED','publicDistributionApproved':True}; m['approval']={'reviewer':'reviewer','approvedAt':'2026-08-15T00:00:00Z'}; m['ssot']={'status':'SYNCED'}; m['quality']={'overall':95,'domains':{}}
  for e in m['manualEvidence']: e['status']='PASS'
  m['fieldMetrics']={'instructorRehearsal':{'plannedMinutes':200,'actualMinutes':200},'studentPilot':{'minimumOutputCompletionPct':90,'saveSubmitSuccessPct':95,'privacyCriticalIncidentCount':0}}
  self.assertIn('QUALITY_DOMAINS_MISSING',lc.release_policy(m))
  m['quality']['domains']={'instructional':90}
  self.assertEqual([],lc.release_policy(m))
  m['fieldMetrics']['studentPilot']['saveSubmitSuccessPct']=89.9
  self.assertIn('SAVE_SUBMIT_SUCCESS_BELOW_90_OR_MISSING',lc.release_policy(m))
 def test_r2_key_is_sha_immutable(self):
  sha='a'*64; self.assertEqual('courses/feed-why/0.4/'+sha+'/deck.pptx',lc.r2_key('feed-why','0.4',sha,'deck.pptx'))
  with self.assertRaises(lc.QAError): lc.r2_key('feed-why','0.4',sha,'../deck.pptx')
 def test_budget_guard_zero_cost_baseline(self):
  q=lc.budget_guard(); self.assertEqual('PASS',q['status'],q)
 def test_impact_contract_changes_require_full(self):
  src=(ROOT/'tools/lessonctl/lessonctl.py').read_text(encoding='utf-8'); self.assertIn("contracts/",src); self.assertIn("recommended':'full'",src)
 def test_html_offline_gate(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'ok.html'; p.write_text('<!doctype html><script>const x=1</script>',encoding='utf-8'); self.assertTrue(lc.html_qa(p)['pass']); p.write_text('<script src="https://example.com/a.js"></script>',encoding='utf-8'); self.assertFalse(lc.html_qa(p)['pass'])
 def test_synthetic_pptx_structure_and_notes(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'s.pptx'; self._make_pptx(p); q=lc.pptx_qa(p); self.assertTrue(q['pass'],q); self.assertEqual(5,q['slides']); self.assertEqual(5,q['notes'])
 def _make_pptx(self,p):
  ct='<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>'
  pres='<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst>'+''.join(f'<p:sldId id="{255+i}" r:id="rId{i}"/>' for i in range(1,6))+'</p:sldIdLst></p:presentation>'
  rels='<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>' for i in range(1,6))+'</Relationships>'
  sld='<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><a:t>학생 행동</a:t></p:cSld></p:sld>'
  sections=''.join(f'<a:t>{x}</a:t>' for x in lc.NOTE_SECTIONS)
  note=f'<p:notes xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">{sections}</p:notes>'
  with zipfile.ZipFile(p,'w') as z:
   z.writestr('[Content_Types].xml',ct); z.writestr('ppt/presentation.xml',pres); z.writestr('ppt/_rels/presentation.xml.rels',rels)
   for i in range(1,6): z.writestr(f'ppt/slides/slide{i}.xml',sld); z.writestr(f'ppt/notesSlides/notesSlide{i}.xml',note)

if __name__=='__main__': unittest.main()
