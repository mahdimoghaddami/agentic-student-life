import unittest,tempfile,csv
from pathlib import Path
from coach.io import write_jsonl,write_json
from coach.evaluation.metrics import summarize_run
from coach.evaluation.human import export_ratings

class EvaluationTests(unittest.TestCase):
    def test_mae_and_blinding(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); rows=[];judges=[]
            for i in range(10):
                rows.append({'case_id':str(i),'config_id':'full','status':'ok','decision':'suggest','final_message':'Example','evaluation_context':{},'is_mock':True,'acceptable_decisions':['suggest'],'trace':{'latency_s':1,'llm_calls':2,'total_tokens':10}})
                judges.append({'case_id':str(i),'config_id':'full','status':'ok','is_mock':True,'scores':{'context_awareness':4,'goal_alignment':3,'clarity':5}})
            write_jsonl(p/'o.jsonl',rows);write_jsonl(p/'j.jsonl',judges)
            export_ratings(p/'o.jsonl',p/'human')
            with (p/'human/ratings.csv').open(newline='') as f: reader=csv.DictReader(f);fields=reader.fieldnames;ratings=list(reader)
            self.assertNotIn('case_id',fields)
            for r in ratings:r.update(context_awareness=3,goal_alignment=3,clarity=3,rated_at='2026-11-03T12:00:00-05:00',rated_before_viewing_llm_scores='yes')
            with (p/'human/ratings.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(ratings)
            m=summarize_run(p/'o.jsonl',p/'j.jsonl',p/'human/ratings.csv',p/'human/private_mapping.json')
            self.assertEqual(m['human_llm_mae_overall'],1)
            self.assertEqual(m['human_llm_mae']['clarity'],2)
            self.assertTrue(m['is_mock'])
