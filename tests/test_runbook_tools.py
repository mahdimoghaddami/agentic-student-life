import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class RunbookToolsTests(unittest.TestCase):
    def test_generated_model_comparison_changes_only_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(os.environ,COACH_PROVIDER='gemini',GEMINI_MODEL='model-a',MODEL_B_PROVIDER='gemini',MODEL_B='model-b')
            subprocess.run([sys.executable,str(ROOT/'tools/setup_experiments.py'),'--base',str(ROOT/'configs/full.json'),'--out','configs'],cwd=tmp,env=env,check=True,capture_output=True)
            a=json.loads((Path(tmp)/'configs/full.json').read_text());b=json.loads((Path(tmp)/'configs/model_b.json').read_text())
            self.assertEqual(a['model'],'model-a');self.assertEqual(b['model'],'model-b')
            self.assertEqual({k:v for k,v in a.items() if k not in ('name','model','provider')},{k:v for k,v in b.items() if k not in ('name','model','provider')})
            self.assertEqual(len(list((Path(tmp)/'configs').glob('*.json'))),12)
    def test_same_model_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(os.environ,COACH_PROVIDER='gemini',GEMINI_MODEL='same',MODEL_B_PROVIDER='gemini',MODEL_B='same')
            r=subprocess.run([sys.executable,str(ROOT/'tools/setup_experiments.py'),'--base',str(ROOT/'configs/full.json'),'--out','configs'],cwd=tmp,env=env,capture_output=True)
            self.assertNotEqual(r.returncode,0)
    def test_history_is_labeled_and_cutoff_safe(self):
        from coach.io import epoch
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'cases.jsonl'
            subprocess.run([sys.executable,str(ROOT/'tools/add_simulated_history.py'),'--cases',str(ROOT/'examples/episodes.jsonl'),'--out',str(target)],capture_output=True) # refuses existing history
            self.assertFalse(target.exists())
            source=Path(tmp)/'source.jsonl'
            rows=[json.loads(l) for l in (ROOT/'examples/episodes.jsonl').read_text().splitlines()]
            for row in rows:row['history']=[]
            source.write_text('\n'.join(map(json.dumps,rows))+'\n')
            subprocess.run([sys.executable,str(ROOT/'tools/add_simulated_history.py'),'--cases',str(source),'--out',str(target)],check=True,capture_output=True)
            result=[json.loads(l) for l in target.read_text().splitlines()]
            self.assertEqual(result[0]['history'],[]);self.assertTrue(result[-1]['history'])
            for row in result:
                self.assertEqual(row['profile']['source'],'simulated_profile')
                for event in row['history']:
                    self.assertEqual(event['source'],'simulated_interaction');self.assertLessEqual(epoch(event['at']),epoch(row['decision_time']))
