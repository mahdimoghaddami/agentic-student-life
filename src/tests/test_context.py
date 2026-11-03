import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from studentlife_context.ema import option_map
from studentlife_context.sensing import _join
from studentlife_context import build_student_context,coaching_signals

BASE=1365000000  # in 2013

def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data),encoding='utf-8')


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        definitions=[
          {'name':'Sleep','questions':[
            {'question_id':'hour','options':'[1]<3, [8]6.5, [9]7, [11]8, '},
            {'question_id':'rate','options':'[1]Very good, [2]Fairly good, [3]Fairly bad, [4]Very bad, '},
            {'question_id':'social','options':'[1]None, [2]Once, [3]Twice, [4]Three or more times, '}]},
          {'name':'Stress','questions':[{'question_id':'level',
             'options':'[1]A little stressed, [2]Definitely stressed, [3]Stressed out, [4]Feeling good, [5]Feeling great, '}]},
          {'name':'Class','questions':[{'question_id':'due','options':'(Yes) 1 2 (No)'}]},
        ]
        dump(self.root/'EMA'/'EMA_definition.json',definitions)
        dump(self.root/'EMA'/'response'/'Sleep'/'Sleep_u00.json',[
            {'null':None,'resp_time':BASE-120},
            {'hour':'8','rate':'1','social':'1','resp_time':BASE-60},
            {'hour':'11','rate':'4','resp_time':BASE+60},
        ])
        dump(self.root/'EMA'/'response'/'Stress'/'Stress_u00.json',[
            {'level':'2','resp_time':BASE-200}])
        dump(self.root/'EMA'/'response'/'Class'/'Class_u00.json',[
            {'due':'1','resp_time':BASE-100}])
        p=self.root/'sensing'/'conversation'/'conversation_u00.csv'
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('start_timestamp,end_timestamp\n'
                     f'{BASE-500},{BASE-400}\n'
                     f'{BASE-450},{BASE-350}\n'
                     f'{BASE-450},{BASE-350}\n'
                     f'{BASE-50},{BASE+10}\n',encoding='utf-8')
        p=self.root/'sensing'/'activity'/'activity_u00.csv'
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(f'timestamp,activity\n{BASE-100},walking\n{BASE-20},1\n',encoding='utf-8')
        p=self.root/'sensing'/'gps'/'gps_u00.csv'
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(f'timestamp,latitude,longitude\n{BASE-100},43.123,-72.456\n',encoding='utf-8')

    def test_decode_time_leakage(self):
        c=build_student_context(self.root,'u00',BASE)
        d=c['observations']['ema']['latest']
        self.assertEqual(d['Sleep.hour']['label'],'6.5')
        self.assertEqual(d['Sleep.hour']['hours'],6.5)
        self.assertEqual(d['Stress.level']['label'],'Definitely stressed')
        self.assertEqual(d['Class.due']['label'],'Yes')
        self.assertEqual(c['observations']['ema']['quality']['after_cutoff'],1)
        self.assertIn('recent_self_reported_stress',[s['type'] for s in coaching_signals(c)])
        self.assertNotIn('recent_short_sleep_report',[s['type'] for s in coaching_signals(c)])

    def test_intervals_and_activity_sampling(self):
        c=build_student_context(self.root,'u00',BASE)
        sensing=c['observations']['sensing']
        self.assertAlmostEqual(sensing['conversation']['detected_conversation_minutes'],150/60)
        self.assertEqual(sensing['conversation']['rows_last_hours'],3)
        self.assertEqual(sensing['activity']['decoded_classification_sample_counts'],{'walking':2})
        self.assertNotIn('gps',sensing)
        self.assertNotIn('43.123',json.dumps(c))
        cg=build_student_context(self.root,'u00',BASE,sensing_streams=['gps'])
        self.assertEqual(cg['observations']['sensing']['gps']['rows_last_hours'],1)
        self.assertNotIn('43.123',json.dumps(cg))
        self.assertNotIn('-72.456',json.dumps(c))

    def test_absent_not_zero(self):
        c=build_student_context(self.root,'u01',BASE)
        self.assertEqual(c['observations']['ema']['latest'],{})
        self.assertTrue(any('Sleep' in x for x in c['missing_or_unavailable']))

    def test_intervals_cross_window_and_codes(self):
        path=self.root/'sensing'/'phonecharge'/'phonecharge_u00.csv'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(f'start_timestamp,end_timestamp\n{BASE-90000},{BASE-87000}\n{BASE-86460},{BASE-86340}\n',encoding='utf-8')
        path=self.root/'sensing'/'audio'/'audio_u00.csv'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(f'timestamp,audio inference\n{BASE-100},1\n{BASE-60},0\n',encoding='utf-8')
        c=build_student_context(self.root,'u00',BASE,sensing_streams=['phonecharge','audio'])
        self.assertEqual(c['observations']['sensing']['phonecharge']['recorded_charging_minutes'],1.0)
        self.assertEqual(c['observations']['sensing']['audio']['decoded_classification_sample_counts'],{'silence':1,'voice':1})

    def test_syllabus_opt_in(self):
        p=self.root/'education'/'deadlines.csv'
        p.parent.mkdir(parents=True,exist_ok=True)
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from datetime import timedelta
        today=datetime.fromtimestamp(BASE,ZoneInfo('America/New_York')).date()
        ds=[(today+timedelta(days=i)).isoformat() for i in range(3)]
        p.write_text('uid,'+','.join(ds)+'\n'+'u00,0,2,1\n',encoding='utf-8')
        c=build_student_context(self.root,'u00',BASE)
        self.assertNotIn('assumed_academic_calendar',c['observations'])
        c=build_student_context(self.root,'u00',BASE,assume_syllabus_known=True)
        d=c['observations']['assumed_academic_calendar']
        self.assertEqual(d['deadline_count_next_days'],3)
        self.assertIn('SIMULATED',d['assumption'])

    def test_options_and_merge(self):
        self.assertEqual(option_map('[1]0-4 persons, [2]5-9 persons, [6]over 100 persons, ')['2'],'5-9 persons')
        self.assertEqual(option_map('(Yes) 1 2 (No)')['2'],'No')
        self.assertEqual(_join([(0,10),(5,20),(0,10),(30,40)]),30)


if __name__=='__main__':unittest.main()
