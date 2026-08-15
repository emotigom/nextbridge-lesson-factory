import json, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/lessonctl'))
from core import QAError
from package_checks import parse_checksums, html_runtime_contract, runtime_report_contract, manifest_contract

class TestPackageContracts(unittest.TestCase):
    def test_checksum_parser_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'c.txt'; p.write_text(('a'*64)+'  a.txt\n'+('b'*64)+'  a.txt\n',encoding='utf-8')
            with self.assertRaises(QAError): parse_checksums(p)

    def test_html_runtime_contract_is_session_only_and_version_locked(self):
        manifest={'runtime':{'appVersion':'1.2.1','buildId':'rc2','schemaVersion':4,'datasetVersion':'2026.08'},'source':{'originalSimulatorSha256':'a'*64}}
        html="""<style>@media print{body{}}</style><button id='reset'></button><button id='import'></button><input id='importFile' type='file'><button id='export'></button><button id='print'></button><button id='run'></button><button id='reveal'></button><input id='mainPrediction'>
<script>const APP_VERSION='1.2.1',BUILD_ID='rc2',SCHEMA_VERSION=4,DATASET_VERSION='2026.08';const SOURCE_SHA256='"""+('a'*64)+"""';const STORE_KEY='x';sessionStorage.setItem('x','1');sessionStorage.getItem('x');URL.createObjectURL(new Blob([]));window.print();function validateEnvelope(){}function sanitizedPayload(){}function configurationChanged(){}function stateAfterPredictionEdit(){}</script>"""
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.html'; p.write_text(html,encoding='utf-8'); self.assertTrue(html_runtime_contract(p,manifest)['sessionOnly'])
            p.write_text(html.replace('sessionStorage.getItem','localStorage.getItem'),encoding='utf-8')
            with self.assertRaises(QAError): html_runtime_contract(p,manifest)

    def test_manifest_contract_requires_all_roles(self):
        golden={'packageVersion':'0.4','expected':{'stage':'TECH_QA','nextStageCandidate':'INSTRUCTOR_PILOT','releaseDecision':'HOLD','prototype':{'slides':5,'notes':5,'overflow':0}}}
        policy={'monthlyIncrementalBudgetUsd':0,'allowLargerRunners':False,'allowWorkersPaid':False,'allowCloudflareContainers':False}
        manifest={'manifestSchemaVersion':'1.0.0','version':'0.4','stage':'TECH_QA','nextStageCandidate':'INSTRUCTOR_PILOT','releaseDecision':'HOLD','runtime':{},'qa':{'runtime':{'status':'PASS'},'prototypePptx':{'slides':5,'notes':5,'overflow':0}},'costPolicy':policy.copy(),'assets':[],'distribution':{'currentPackagePublicCommitAllowed':False},'quality':{'status':'NOT_SCORED'},'rights':{'status':'UNVERIFIED'}}
        with self.assertRaises(QAError): manifest_contract(manifest,golden,policy)

    def test_runtime_report_requires_named_safety_checks(self):
        required=['externalDependencies','networkApis','sessionOnlyStorage','importSchemaRejected','importBooleanTypesRejected','importWeightTypesRejected','nestedEvidenceRejected','importRoundTripEvidence','staleTestInvalidation','predictionReasonGate','predictionEditInvalidates','mainPredictionStateTransition','finalOnlyPrintCss']
        expected={'runtimeChecks':{'total':13,'supportedMatrixTotal':108}}
        report={'status':'PASS','failures':[],'sha256':'a'*64,'versions':{'app':'1','build':'b','schema':4,'dataset':'d'},'checks':{k:True for k in required},'details':{'matrixCases':108,'matrixFailures':[]}}
        manifest={'runtime':{'appVersion':'1','buildId':'b','schemaVersion':4,'datasetVersion':'d'},'qa':{'runtime':{'subjectSha256':'a'*64,'checks':13}}}
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r.json'; p.write_text(json.dumps(report),encoding='utf-8')
            self.assertEqual(13,runtime_report_contract(p,{'sha256':'a'*64},manifest,expected)['checkCount'])
            del report['checks']['predictionReasonGate']; p.write_text(json.dumps(report),encoding='utf-8')
            with self.assertRaises(QAError): runtime_report_contract(p,{'sha256':'a'*64},manifest,expected)

if __name__=='__main__': unittest.main()
