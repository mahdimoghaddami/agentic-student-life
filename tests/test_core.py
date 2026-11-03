import unittest,tempfile,json,csv,threading
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,HTTPServer
from coach.io import read_jsonl,write_jsonl,write_json
from coach.data.features import summarize,merge_minutes
from coach.data.importer import import_dataset
from coach.config import Config
from coach.memory import Memory
from coach.orchestrator import run_case
from coach.runner import run
from coach.ablations import configurations
from coach.models import Model

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.case=read_jsonl('examples/cases.jsonl')[1];self.records=read_jsonl('examples/observations.jsonl')
    def tearDown(self):self.tmp.cleanup()
    def execute(self,cfg=None,case=None,records=None):
        m=Memory(self.root/'memory.sqlite')
        try:return run_case(case or self.case,records if records is not None else self.records,cfg or Config(provider='mock'),m,'test')
        finally:m.close()
    def test_future_submission_excluded(self):
        r={'id':'future','participant_id':'demo_u01','stream':'sleep','observed_at':'2013-04-14T00:00:00+00:00','available_at':'2013-04-16T00:00:00+00:00','value':1,'source':'simulated_observation'}
        self.assertTrue(summarize([r],'demo_u01',self.case['decision_time'])['sleep']['missing'])
    def test_overlap_and_missing(self):
        self.assertEqual(merge_minutes([(0,120),(60,180),(0,120)]),3)
        self.assertTrue(summarize([],'x',self.case['decision_time'])['conversation']['missing'])
    def test_preference_update(self):
        out,_=self.execute();self.assertIn('stretch',out['final_message']);self.assertEqual(out['status'],'ok')
    def test_future_preference_excluded(self):
        c=dict(self.case,history=[dict(self.case['history'][0],at='2014-01-01T00:00:00+00:00')])
        out,_=self.execute(case=c);self.assertNotIn('stretch',out['final_message'])
    def test_ablations_cover_required_budgets(self):
        cfgs=configurations(Config(provider='mock'),'mock','mock')
        self.assertEqual(len(cfgs),9)
        self.assertEqual({x.planning_rounds for x in cfgs},{0,1,2,3})
        self.assertEqual({x.reflection_cycles for x in cfgs},{0,1,2,3})
    def test_disabled_stages_and_tool_logs(self):
        out,trace=self.execute(Config(provider='mock',planning_rounds=0,reflection_cycles=0))
        self.assertEqual(out['trace']['llm_calls'],1)
        out,trace=self.execute();self.assertTrue(any(x['type']=='tool' for x in trace['events']))
    def test_episode_memory_persists(self):
        m=Memory(self.root/'episode.sqlite');cases=read_jsonl('examples/episodes.jsonl')
        try:
            rows=[run_case(c,self.records,Config(provider='mock'),m,'episode')[0] for c in cases]
        finally:m.close()
        self.assertIn('stretch',rows[1]['final_message']);self.assertIn('small next step',rows[2]['final_message'])
        self.assertEqual(rows[2]['evaluation_context']['profile']['preferred_activity'],'stretching')
    def test_isolated_cases(self):
        out=self.root/'run';run('examples/cases.jsonl','examples/observations.jsonl',Config(provider='mock'),out)
        self.assertEqual(len(read_jsonl(out/'outputs.jsonl')),16)
        with self.assertRaises(ValueError):run('examples/cases.jsonl','examples/observations.jsonl',Config(provider='mock'),out)
    def test_model_failure_recorded(self):
        with patch('coach.models.Model.ask',side_effect=ValueError('bad response')):
            out,_=self.execute()
        self.assertEqual(out['status'],'failed');self.assertIsNone(out['decision'])
    def test_reflection_budget_and_revision(self):
        from coach.mock import respond
        def fake(stage,payload):
            if stage=='review':return {'accept':False,'issues':['Use latest preference'],'revision_request':'Revise'}
            return respond(stage,payload)
        with patch('coach.models.respond',side_effect=fake):
            out,trace=self.execute(Config(provider='mock',reflection_cycles=3))
        self.assertEqual(out['trace']['reflection_cycles'],3)
        self.assertEqual(sum(x['stage']=='revise' for x in trace['model_calls']),3)
    def test_planning_budget(self):
        from coach.mock import respond
        def fake(stage,payload):
            result=respond(stage,payload)
            if stage=='plan' and 'ready' in result:result['ready']=False;result['information_gaps']=['Need more context']
            return result
        with patch('coach.models.respond',side_effect=fake):out,_=self.execute(Config(provider='mock',planning_rounds=3))
        self.assertEqual(out['trace']['planning_rounds'],3)
    def test_import_explicit_decoding(self):
        import hashlib
        (self.root/'EMA/response/Sleep').mkdir(parents=True)
        write_json(self.root/'EMA/EMA_definition.json',{'fixture':True})
        write_json(self.root/'EMA/response/Sleep/Sleep_u00.json',[{'resp_time':1366000000,'hour':9}])
        mapping={'ema_definition_sha256':hashlib.sha256((self.root/'EMA/EMA_definition.json').read_bytes()).hexdigest(),'streams':{'sleep':{'glob':'EMA/response/Sleep/*.json','observed_field':'resp_time','available_field':'resp_time','value_field':'hour','values':{'9':7}}}}
        write_json(self.root/'mapping.json',mapping);import_dataset(self.root,self.root/'mapping.json',self.root/'obs.jsonl')
        self.assertEqual(read_jsonl(self.root/'obs.jsonl')[0]['value'],7)
        mapping['streams']['sleep']['values']={};write_json(self.root/'mapping.json',mapping)
        with self.assertRaises(ValueError):import_dataset(self.root,self.root/'mapping.json',self.root/'bad.jsonl')
        self.assertFalse((self.root/'bad.jsonl').exists())

class HTTPTests(unittest.TestCase):
    def test_provider_wire_formats(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append((self.path,body))
                content=json.dumps({'ok':True})
                response={'message':{'content':content},'prompt_eval_count':11,'eval_count':7} if self.path=='/api/chat' else {'choices':[{'message':{'content':content}}],'usage':{'total_tokens':19}}
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(response).encode())
        server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with patch.dict('os.environ',{'OLLAMA_BASE_URL':base,'GEMINI_BASE_URL':base+'/v1','GEMINI_API_KEY':'test-only'}):
                a=Model('ollama','fixture');b=Model('gemini','openai:fixture')
                self.assertTrue(a.ask('draft','test',{})['ok']);self.assertTrue(b.ask('draft','test',{})['ok'])
                self.assertEqual(a.calls[0]['total_tokens'],18);self.assertEqual(b.calls[0]['total_tokens'],19)
                self.assertEqual(requests[1][1]['model'],'fixture')
        finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
