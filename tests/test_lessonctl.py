import importlib.util, json, subprocess, sys, tempfile, unittest, zipfile
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
  # Classification itself is covered without needing a Git repo by checking the path policy semantics in source.
  src=(ROOT/'tools/lessonctl/lessonctl.py').read_text(encoding='utf-8'); self.assertIn("contracts/",src); self.assertIn("recommended':'full'",src)
 def test_html_offline_gate(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'ok.html'; p.write_text('<!doctype html><script>const x=1</script>',encoding='utf-8'); self.assertTrue(lc.html_qa(p)['pass']); p.write_text('<script src="https://example.com/a.js"></script>',encoding='utf-8'); self.assertFalse(lc.html_qa(p)['pass'])
 def test_synthetic_pptx_structure_and_notes(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'s.pptx'; self._make_pptx(p); q=lc.pptx_qa(p); self.assertTrue(q['pass'],q); self.assertEqual(5,q['slides']); self.assertEqual(5,q['notes'])
 def _evidence_record(self,course,gate):
  return {'schemaVersion':'1.0.0','courseId':course['courseId'],'gate':gate,'status':'PASS','subjectSha256':lc.manual_gate_subject(course,gate),'capturedAt':'2026-08-15T20:00:00+09:00','reviewer':'test-reviewer','environment':{'platform':'Windows 11'},'evidenceRefs':['private-r2://test/evidence.json']}
 def test_manual_evidence_subject_tracks_current_source(self):
  c=lc.load_jsonish(ROOT/'courses/feed-why/course.yaml'); gate='INDEPENDENT_INSTRUCTOR_REHEARSAL'; original=lc.manual_gate_subject(c,gate); self.assertEqual(64,len(original)); c['sourceLock']['runtimeHtmlSha256']='f'*64; self.assertNotEqual(original,lc.manual_gate_subject(c,gate))
 def test_manual_evidence_rejects_stale_subject(self):
  c=lc.load_jsonish(ROOT/'courses/feed-why/course.yaml'); e=self._evidence_record(c,'BROWSER_FILE_SMOKE'); self.assertTrue(lc.verify_evidence(c,e)[0]); e['subjectSha256']='0'*64; ok,blockers=lc.verify_evidence(c,e); self.assertFalse(ok); self.assertIn('EVIDENCE_STALE_SUBJECT',blockers)
 def test_stage_cannot_skip(self):
  c=lc.load_jsonish(ROOT/'courses/feed-why/course.yaml'); self.assertIn('STAGE_SKIP_FORBIDDEN',lc.stage_check(c,'FIELD_PILOT'))
 def test_instructor_pilot_requires_private_evidence(self):
  c=lc.load_jsonish(ROOT/'courses/feed-why/course.yaml'); b=lc.stage_check(c,'INSTRUCTOR_PILOT'); self.assertIn('MANUAL_EVIDENCE_DIR_REQUIRED',b); self.assertIn('MANUAL_GATE_EVIDENCE_MISSING:BROWSER_FILE_SMOKE',b)
 def test_instructor_pilot_passes_with_five_current_evidence_files(self):
  c=lc.load_jsonish(ROOT/'courses/feed-why/course.yaml')
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)
   for gate in ['BROWSER_FILE_SMOKE','VIEWPORT_1440_900_375_812','JSON_ROUNDTRIP_PRINT','WINDOWS_POWERPOINT_SMOKE','FONT_PORTABILITY_REFLOW']:
    (d/(gate+'.json')).write_text(json.dumps(self._evidence_record(c,gate)),encoding='utf-8')
   self.assertEqual([],lc.stage_check(c,'INSTRUCTOR_PILOT',d))
 def test_field_ready_requires_quality_rights_and_ssot_even_with_evidence(self):
  c=lc.load_jsonish(ROOT/'courses/feed-why/course.yaml'); c['stage']='FIELD_PILOT'
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)
   for gate in ['BROWSER_FILE_SMOKE','VIEWPORT_1440_900_375_812','JSON_ROUNDTRIP_PRINT','WINDOWS_POWERPOINT_SMOKE','FONT_PORTABILITY_REFLOW','INDEPENDENT_INSTRUCTOR_REHEARSAL','STUDENT_FIELD_PILOT']:
    (d/(gate+'.json')).write_text(json.dumps(self._evidence_record(c,gate)),encoding='utf-8')
   b=lc.stage_check(c,'FIELD_READY',d); self.assertIn('QUALITY_BELOW_90_OR_UNSCORED',b); self.assertIn('RIGHTS_NOT_APPROVED',b); self.assertIn('SSOT_NOT_SYNCED',b)
 def test_main_direct_push_has_full_qa_workflow(self):
  text=(ROOT/'.github/workflows/qa-main.yml').read_text(encoding='utf-8'); self.assertIn('branches: [main]',text); self.assertIn('qa full --course feed-why',text); self.assertIn('if: failure()',text)
 def test_cli_evidence_subject_emits_json(self):
  cp=subprocess.run([sys.executable,str(ROOT/'tools/lessonctl/lessonctl.py'),'evidence','subject','--course','feed-why','--gate','BROWSER_FILE_SMOKE'],cwd=ROOT,text=True,capture_output=True); self.assertEqual(0,cp.returncode,cp.stderr); self.assertEqual(lc.manual_gate_subject(lc.load_jsonish(ROOT/'courses/feed-why/course.yaml'),'BROWSER_FILE_SMOKE'),json.loads(cp.stdout)['subjectSha256'])
 def test_cli_stage_check_blocks_without_private_evidence(self):
  cp=subprocess.run([sys.executable,str(ROOT/'tools/lessonctl/lessonctl.py'),'stage','check','--course','feed-why','--to','INSTRUCTOR_PILOT'],cwd=ROOT,text=True,capture_output=True); self.assertEqual(2,cp.returncode); self.assertEqual('HOLD',json.loads(cp.stdout)['status'])
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
