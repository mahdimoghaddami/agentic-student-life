import io,json,os,unittest
from unittest.mock import patch
from urllib.error import HTTPError
from coach.models import Model,_BLOCKED,_LAST_REQUEST
from coach.key_pool import _CURSOR,_DISABLED
from coach.credentials import gemini_pool

def error(code=429,message='minute quota',retry=None):
    return HTTPError('https://example.invalid',code,'error',{'Retry-After':str(retry)} if retry else {},io.BytesIO(json.dumps({'error':{'message':message}}).encode()))
def response():return io.BytesIO(b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}],"usage":{"total_tokens":7}}')
class PoolTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'GEMINI_KEY_MODE':'auto','GEMINI_API_KEY_1':'secret-one','GEMINI_API_KEY_2':'secret-two','GEMINI_MIN_INTERVAL_SECONDS':'0','GEMINI_MAX_RETRIES':'1','GEMINI_MAX_RETRY_WAIT_SECONDS':'120'},clear=True);self.env.start()
        for d in (_BLOCKED,_LAST_REQUEST,_CURSOR,_DISABLED):d.clear()
    def tearDown(self):
        self.env.stop()
        for d in (_BLOCKED,_LAST_REQUEST,_CURSOR,_DISABLED):d.clear()
    def test_switch_and_sticky_success(self):
        names=[]
        def send(request,**kw):
            names.append(request.get_header('Authorization'))
            if len(names)==1:raise error()
            return response()
        with patch('urllib.request.urlopen',side_effect=send):
            a=Model('gemini','same-model');a.ask('draft','s',{})
            b=Model('gemini','same-model');b.ask('draft','s',{})
        self.assertEqual(names,['Bearer secret-one','Bearer secret-two','Bearer secret-two'])
        self.assertEqual([r['credential_name'] for r in a.calls],['GEMINI_API_KEY_1','GEMINI_API_KEY_2'])
        self.assertNotIn('secret-one',json.dumps(a.calls));self.assertNotIn('secret-two',json.dumps(a.calls))
    def test_all_daily_exhausted_not_repeated(self):
        with patch('urllib.request.urlopen',side_effect=lambda *a,**kw: (_ for _ in ()).throw(error(message='daily quota'))) as send:
            for _ in range(2):
                with self.assertRaises(RuntimeError):Model('gemini','fixture').ask('draft','s',{})
            self.assertEqual(send.call_count,2)
    def test_shared_project_skipped(self):
        os.environ.update(GEMINI_PROJECT_ID_1='same',GEMINI_PROJECT_ID_2='same',GEMINI_API_KEY_3='secret-three',GEMINI_PROJECT_ID_3='different')
        with patch('urllib.request.urlopen',side_effect=[error(message='daily quota'),response()]):
            m=Model('gemini','fixture');m.ask('draft','s',{})
        self.assertEqual([r['credential_name'] for r in m.calls],['GEMINI_API_KEY_1','GEMINI_API_KEY_3'])
    def test_auth_failure_disabled_and_400_not_retried(self):
        with patch('urllib.request.urlopen',side_effect=[error(401),response()]):
            Model('gemini','fixture').ask('draft','s',{})
        self.assertEqual(len(_DISABLED),1)
        with patch('urllib.request.urlopen',side_effect=error(400)) as send:
            with self.assertRaises(RuntimeError):Model('gemini','fixture').ask('draft','s',{})
            self.assertEqual(send.call_count,1)
    def test_cycle_after_cooldown_and_retry_after(self):
        clock=[100.];sleeps=[]
        def sleep(t):clock[0]+=t;sleeps.append(t)
        with patch('time.monotonic',side_effect=lambda:clock[0]),patch('time.sleep',side_effect=sleep),patch('urllib.request.urlopen',side_effect=[error(retry=90),error(retry=90),response()]):
            m=Model('gemini','fixture');m.ask('draft','s',{})
        self.assertEqual(sleeps,[90]);self.assertEqual([r['credential_name'] for r in m.calls],['GEMINI_API_KEY_1','GEMINI_API_KEY_2','GEMINI_API_KEY_1'])
    def test_deduplicate_and_numeric_sort(self):
        os.environ.update(GEMINI_API_KEY_10='secret-ten',GEMINI_API_KEY='secret-one')
        self.assertEqual([x[0] for x in gemini_pool()],['GEMINI_API_KEY_1','GEMINI_API_KEY_2','GEMINI_API_KEY_10'])
    def test_wait_budget_and_attempt_budget(self):
        os.environ['GEMINI_MAX_RETRY_WAIT_SECONDS']='5'
        with patch('urllib.request.urlopen',side_effect=lambda *a,**kw: (_ for _ in ()).throw(error(retry=600))) as send,patch('time.sleep') as sleep:
            with self.assertRaises(RuntimeError):Model('gemini','fixture').ask('draft','s',{})
            self.assertEqual(send.call_count,2);sleep.assert_not_called()
