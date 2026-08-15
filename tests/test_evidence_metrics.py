import json, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/lessonctl'))
from core import load_jsonish
from evidence import evidence_plan, metric_blockers, verify_evidence
from release_policy import manual_gate_subject

class TestEvidenceMetrics(unittest.TestCase):
    def setUp(self): self.course=load_jsonish(ROOT/'courses/feed-why/course.yaml')
    def record(self,gate,metrics):
        return {'schemaVersion':'1.0.0','courseId':'feed-why','gate':gate,'status':'PASS','subjectSha256':manual_gate_subject(self.course,gate),'capturedAt':'2026-08-15T20:00:00+09:00','reviewer':'reviewer','environment':{'platform':'Windows 11'},'evidenceRefs':['private-r2://evidence'],'metrics':metrics}
    def test_browser_requires_both_browsers_and_zero_console_errors(self):
        good={'chromePass':True,'edgePass':True,'chromeConsoleErrors':0,'edgeConsoleErrors':0,'fileProtocolPass':True}
        self.assertEqual([],metric_blockers('BROWSER_FILE_SMOKE',good))
        bad=dict(good); bad['edgeConsoleErrors']=1
        self.assertIn('EVIDENCE_METRIC_NOT_0:edgeConsoleErrors',metric_blockers('BROWSER_FILE_SMOKE',bad))
    def test_rehearsal_enforces_plus_minus_ten_percent(self):
        good={'plannedMinutes':200,'actualMinutes':218,'rescueWithin3MinPass':True}
        self.assertEqual([],metric_blockers('INDEPENDENT_INSTRUCTOR_REHEARSAL',good))
        bad=dict(good); bad['actualMinutes']=221
        self.assertIn('EVIDENCE_REHEARSAL_OUTSIDE_10_PERCENT',metric_blockers('INDEPENDENT_INSTRUCTOR_REHEARSAL',bad))
    def test_student_pilot_thresholds(self):
        good={'minimumOutputCompletionPct':85,'saveSubmitSuccessPct':90,'privacyCriticalIncidentCount':0}
        self.assertTrue(verify_evidence(self.course,self.record('STUDENT_FIELD_PILOT',good))[0])
        bad=dict(good); bad['minimumOutputCompletionPct']=84.9
        ok,blockers=verify_evidence(self.course,self.record('STUDENT_FIELD_PILOT',bad)); self.assertFalse(ok); self.assertIn('EVIDENCE_METRIC_BELOW_85:minimumOutputCompletionPct',blockers)
    def test_powerpoint_recovery_dialog_is_hard_failure(self):
        good={'openPass':True,'notesPass':True,'slideshowPass':True,'pdfExportPass':True,'saveReopenPass':True,'recoveryDialogCount':0}
        self.assertTrue(verify_evidence(self.course,self.record('WINDOWS_POWERPOINT_SMOKE',good))[0])
        bad=dict(good); bad['recoveryDialogCount']=1
        self.assertFalse(verify_evidence(self.course,self.record('WINDOWS_POWERPOINT_SMOKE',bad))[0])
    def test_plan_exposes_current_subjects_and_required_metrics(self):
        plan=evidence_plan('feed-why'); self.assertEqual(7,len(plan['gates'])); browser=plan['gates'][0]; self.assertEqual(self.course['sourceLock']['runtimeHtmlSha256'],browser['subjectSha256']); self.assertIn('chromeConsoleErrors',browser['requiredMetrics'])

if __name__=='__main__': unittest.main()
