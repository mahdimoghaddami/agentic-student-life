import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from coach.data.contexts import load_contexts
from coach.io import write_jsonl,read_jsonl
from coach.runner import run
from coach.config import Config
from coach.ablations import configurations
from coach.models import Model
from studentlife_context.common import read_records
from studentlife_context.ema import summarize_ema

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.case={'case_id':'real_1','participant_id':'u00','decision_time':'2013-04-15T09:00:00-04:00',
                   'profile':{'source':'simulated_profile'},'history':[]}
        self.ctx={'case_id':'real_1','participant_id':'u00','decision_time':self.case['decision_time'],'status':'ok',
          'observations':{'ema':{'latest':{'Exercise.have':{'code':'1','label':'Yes','observed_at':'2013-04-15T08:00:00-04:00'}},'quality':{'after_cutoff':100}},
                          'sensing':{'activity':{'missing':False,'excluded_future_rows':300,'invalid_rows':1}}},
          'evidence':[{'source':'EMA/Exercise','value':'Yes','observed_at':'2013-04-15T08:00:00-04:00'}],
          'missing_or_unavailable':[],'provenance':{'source':'StudentLife'}}
        self.cases=self.root/'cases.jsonl';self.contexts=self.root/'contexts.jsonl'
        write_jsonl(self.cases,[self.case]);write_jsonl(self.contexts,[self.ctx])
    def test_diagnostics_never_reach_agents(self):
        result=load_contexts(self.contexts,[self.case])['real_1']
        self.assertNotIn('quality',result['observations']['ema'])
        self.assertNotIn('excluded_future_rows',result['observations']['sensing']['activity'])
        self.assertNotIn('invalid_rows',result['observations']['sensing']['activity'])
    def test_identity_and_future_checks(self):
        for kind in ('participant','time','future','failed','missing'):
            with self.subTest(kind=kind):
                row=copy.deepcopy(self.ctx)
                if kind=='participant':row['participant_id']='u01'
                elif kind=='time':row['decision_time']='2013-04-16T09:00:00-04:00'
                elif kind=='future':row['evidence'][0]['observed_at']='2013-04-16T09:00:00-04:00'
                elif kind=='failed':row['status']='error'
                else:row['case_id']='other'
                write_jsonl(self.contexts,[row])
                with self.assertRaises(ValueError):load_contexts(self.contexts,[self.case])
    def test_identical_context_in_all_nine_configurations(self):
        payloads=[];original=Model.ask
        def capture(model,stage,system,payload):
            payloads.append((stage,payload));return original(model,stage,system,payload)
        with patch.object(Model,'ask',capture):
            for cfg in configurations(Config(provider='mock'),'mock','mock'):
                result=run(self.cases,None,cfg,self.root/cfg.name,contexts_path=self.contexts)
                self.assertEqual(result['successful'],1)
        expected=load_contexts(self.contexts,[self.case])['real_1']
        self.assertTrue({'plan','draft','review'}<={stage for stage,_ in payloads})
        for _,payload in payloads:
            self.assertEqual(payload['context']['extended_observations'],expected)
            self.assertIn('get_extended_observations',payload['tools'])
        manifest=json.loads((self.root/'full/manifest.json').read_text())
        self.assertEqual(manifest['inputs'][str(self.contexts)],hashlib.sha256(self.contexts.read_bytes()).hexdigest())
    def test_unknown_code_and_malformed_file_visible(self):
        path=self.root/'bad.json';path.write_text('{')
        with self.assertRaises(ValueError):list(read_records(path))
        (self.root/'EMA/response/Stress').mkdir(parents=True)
        (self.root/'EMA/EMA_definition.json').write_text(json.dumps([{'name':'Stress','questions':[{'question_id':'level','options':'[1]A little stressed'}]}]))
        (self.root/'EMA/response/Stress/Stress_u00.json').write_text(json.dumps([{'resp_time':1366000000,'level':'99'}]))
        with self.assertRaises(ValueError):summarize_ema(self.root,'u00',1366000100)
    def test_conditional_answers(self):
        (self.root/'EMA/response/Mood').mkdir(parents=True)
        (self.root/'EMA/EMA_definition.json').write_text(json.dumps([{'name':'Mood','questions':[{'question_id':'happyornot','options':'(Yes) 1 2 (No)'},{'question_id':'happy','options':'[1]a little bit, [4]extremely'}]}]))
        (self.root/'EMA/response/Mood/Mood_u00.json').write_text(json.dumps([{'resp_time':1366000000,'happyornot':'2','happy':'4'}]))
        result=summarize_ema(self.root,'u00',1366000100)
        self.assertNotIn('Mood.happy',result['latest'])
        self.assertEqual(result['latest']['Mood.happyornot']['label'],'No')
