import unittest,os,json,io
from unittest.mock import patch
from coach.credentials import gemini_credential
from coach.models import Model,_redact,_BLOCKED,_LAST_REQUEST
class CredentialsTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{},clear=True);self.env.start();_BLOCKED.clear();_LAST_REQUEST.clear()
    def tearDown(self):self.env.stop();_BLOCKED.clear();_LAST_REQUEST.clear()
    def test_legacy(self):
        os.environ['GEMINI_API_KEY']='original'
        self.assertEqual(gemini_credential(),('GEMINI_API_KEY','original'))
    def test_arbitrary_slot(self):
        os.environ.update(GEMINI_API_KEY_42='fortytwo',GEMINI_KEY_SLOT='42')
        self.assertEqual(gemini_credential(),('GEMINI_API_KEY_42','fortytwo'))
    def test_missing_selected_key_does_not_fallback(self):
        os.environ.update(GEMINI_API_KEY='original',GEMINI_KEY_SLOT='2')
        with self.assertRaisesRegex(ValueError,'GEMINI_API_KEY_2'):gemini_credential()
    def test_invalid_slot(self):
        os.environ['GEMINI_KEY_SLOT']='../key'
        with self.assertRaises(ValueError):gemini_credential()
    def test_redact_all_keys(self):
        os.environ.update(GEMINI_API_KEY='secretA',GEMINI_API_KEY_1='secretAB',GEMINI_API_KEY_2='secretC')
        self.assertEqual(_redact('secretAB secretA secretC'),'[REDACTED] [REDACTED] [REDACTED]')
    def test_selected_key_in_request_only(self):
        os.environ.update(GEMINI_API_KEY_2='second-secret',GEMINI_KEY_SLOT='2',GEMINI_MIN_INTERVAL_SECONDS='0')
        def response(request,**kwargs):
            self.assertEqual(request.get_header('Authorization'),'Bearer second-secret')
            return io.BytesIO(b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}],"usage":{"total_tokens":2}}')
        with patch('urllib.request.urlopen',side_effect=response):
            m=Model('gemini','fixture');self.assertTrue(m.ask('draft','test',{})['ok'])
        self.assertEqual(m.calls[0]['credential_name'],'GEMINI_API_KEY_2')
        self.assertNotIn('second-secret',json.dumps(m.calls))
