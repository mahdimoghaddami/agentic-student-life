import io,json,unittest
from unittest.mock import patch
from urllib.error import HTTPError
from coach.models import Model,_BLOCKED,_LAST_REQUEST

def error(message='Minute quota exceeded',details=None,headers=None):
    return HTTPError('https://example.invalid',429,'limit',headers or {},io.BytesIO(json.dumps({'error':{'status':'RESOURCE_EXHAUSTED','message':message,'details':details or []}}).encode()))
class Response(io.BytesIO):
    def __init__(self):super().__init__(json.dumps({'choices':[{'message':{'content':'{"ok":true}'}}],'usage':{'total_tokens':7}}).encode())
class RateLimitTests(unittest.TestCase):
    def setUp(self):
        _BLOCKED.clear();_LAST_REQUEST.clear()
        self.env=patch.dict('os.environ',{'GEMINI_API_KEY':'test-secret','GEMINI_MIN_INTERVAL_SECONDS':'0','GEMINI_MAX_RETRIES':'2','GEMINI_RETRY_BASE_SECONDS':'0','GEMINI_MAX_RETRY_WAIT_SECONDS':'120'})
        self.env.start()
    def tearDown(self):self.env.stop();_BLOCKED.clear();_LAST_REQUEST.clear()
    def test_transient_retries_counted(self):
        m=Model('gemini','fixture')
        with patch('urllib.request.urlopen',side_effect=[error(),Response()]),patch('coach.models.time.sleep'):
            self.assertTrue(m.ask('draft','test',{})['ok'])
        self.assertEqual(len(m.calls),2);self.assertIsNone(m.calls[0]['total_tokens']);self.assertEqual(m.calls[1]['total_tokens'],7)
    def test_daily_quota_no_retry_and_circuit(self):
        with patch('urllib.request.urlopen',side_effect=error(details=[{'violations':[{'quotaId':'RequestsPerDay','quotaValue':'20'}]}])) as send:
            for _ in range(2):
                with self.assertRaises(RuntimeError):Model('gemini','fixture').ask('draft','test',{})
            self.assertEqual(send.call_count,1)
    def test_retry_after_honored(self):
        m=Model('gemini','fixture')
        with patch('urllib.request.urlopen',side_effect=[error(headers={'Retry-After':'30'}),Response()]),patch('coach.models.time.sleep') as sleep:
            m.ask('draft','test',{});sleep.assert_called_with(30)
    def test_excessive_wait_not_retried_early(self):
        with patch('urllib.request.urlopen',side_effect=error(headers={'Retry-After':'600'})) as send,patch('coach.models.time.sleep') as sleep:
            with self.assertRaises(RuntimeError):Model('gemini','fixture').ask('draft','test',{})
            self.assertEqual(send.call_count,1);sleep.assert_not_called()
    def test_secret_redacted(self):
        with patch('urllib.request.urlopen',side_effect=error('daily quota for test-secret')):
            with self.assertRaises(RuntimeError) as caught:Model('gemini','fixture').ask('draft','test',{})
            self.assertNotIn('test-secret',str(caught.exception));self.assertIn('[REDACTED]',str(caught.exception))
    def test_pacing_shared_across_instances(self):
        with patch.dict('os.environ',{'GEMINI_MIN_INTERVAL_SECONDS':'10'}),patch('urllib.request.urlopen',side_effect=[Response(),Response()]),patch('coach.models.time.monotonic',return_value=100),patch('coach.models.time.sleep') as sleep:
            Model('gemini','fixture').ask('draft','test',{});Model('gemini','fixture').ask('draft','test',{})
            sleep.assert_called_once_with(10)
