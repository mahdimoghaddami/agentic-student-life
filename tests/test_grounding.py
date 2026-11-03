import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from coach.data.contexts import agent_context
from coach.data.grounding import grounding_issues,registry
from coach.config import Config
from coach.memory import Memory
from coach.orchestrator import run_case

class GroundingTests(unittest.TestCase):
    def context(self,stamp='2013-03-28T00:00:52+00:00',decision='2013-03-28T09:00:00-04:00'):
        row={'participant_id':'u02','decision_time':decision,'observations':{'ema':{'latest':{
            'Class.due':{'source':'EMA/Class','observed_at':stamp,'label':'Yes','question':'Due today?'},
            'Sleep.hour':{'source':'EMA/Sleep','observed_at':stamp,'label':'6.5','hours':6.5}}}},
            'evidence':[],'missing_or_unavailable':[],'provenance':{}}
        return {'extended_observations':agent_context(row),'profile':{'source':'simulated_profile'},'observations':{},'history':[]}
    def draft(self,context,message='You reported an assignment due on March 27.'):
        item=context['extended_observations']['observations']['ema']['latest']['Class.due']
        return {'decision':'suggest','final_message':message,'evidence':[{'source':item['source'],'id':item['id'],'detail':message}]}
    def test_utc_date_is_not_local_date(self):
        c=self.context();item=c['extended_observations']['observations']['ema']['latest']['Class.due']
        self.assertEqual(item['reference_date'],'2013-03-27');self.assertFalse(item['applies_to_decision_day'])
        self.assertTrue(grounding_issues(self.draft(c,'You have an assignment due today.'),c))
        self.assertFalse(grounding_issues(self.draft(c),c))
    def test_same_day_and_dst(self):
        c=self.context(stamp='2013-03-28T04:07:51+00:00')
        self.assertFalse(grounding_issues(self.draft(c,'You reported an assignment due today.'),c))
        c=self.context(stamp='2013-03-10T04:30:00+00:00',decision='2013-03-10T09:00:00-04:00')
        self.assertEqual(c['extended_observations']['observations']['ema']['latest']['Class.due']['reference_date'],'2013-03-09')
    def test_stable_ids_and_source_validation(self):
        c=self.context();self.assertEqual(registry(c),registry(self.context()))
        d=self.draft(c);d['evidence'][0]['id']='Class.due'
        self.assertTrue(grounding_issues(d,c))
        d=self.draft(c);d['evidence'][0]['source']='EMA/Sleep'
        self.assertTrue(grounding_issues(d,c))
    def test_sleep_scope_and_no_duplication(self):
        e=self.context()['extended_observations']
        self.assertNotIn('evidence',e)
        self.assertEqual(e['observations']['ema']['latest']['Sleep.hour']['time_scope'],'retrospective_sleep_report_exact_night_unverified')
    def test_generic_offer_today_not_deadline_claim(self):
        c=self.context()
        for message in ('Would help planning your work today be useful?', 'Do you have anything due today?', 'Today’s deadlines are unknown.'):
            self.assertFalse(grounding_issues(self.draft(c,message),c))
    def test_guard_shared_with_no_reflection_and_budget_preserved(self):
        c=self.context();case={'case_id':'x','participant_id':'u02','decision_time':'2013-03-28T09:00:00-04:00','profile':c['profile'],'history':[]}
        def respond(stage,payload):
            if stage=='review':return {'accept':True,'issues':[],'revision_request':''}
            if stage=='revise':return self.draft(c)
            return self.draft(c,'You have an assignment due today.')
        with tempfile.TemporaryDirectory() as tmp:
            memory=Memory(Path(tmp)/'m.sqlite')
            try:
                with patch('coach.models.respond',side_effect=respond):
                    failed,trace=run_case(case,[],Config(provider='mock',planning_rounds=0,reflection_cycles=0),memory,'a',c['extended_observations'])
                    revised,trace2=run_case(case,[],Config(provider='mock',planning_rounds=0,reflection_cycles=1),memory,'b',c['extended_observations'])
                self.assertEqual(failed['status'],'failed');self.assertIn('Grounding validation failed',failed['error'])
                self.assertEqual(revised['status'],'ok');self.assertEqual(revised['trace']['reflection_cycles'],1)
                review=next(e for e in trace2['events'] if e['type']=='review')
                self.assertTrue(review['model_review']['accept']);self.assertFalse(review['review']['accept'])
            finally:memory.close()
