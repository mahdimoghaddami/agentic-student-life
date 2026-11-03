import json,os,time,urllib.request,urllib.error
from .config import resolve_model
from .mock import respond
class Model:
    def __init__(self,provider,model,temperature=0,max_tokens=1200):
        self.provider,self.model=resolve_model(provider,model)
        self.temperature,self.max_tokens=temperature,max_tokens
        self.calls=[]
    def ask(self,stage,system,payload):
        rec={'type':'model','stage':stage,'provider':self.provider,'model':self.model,'temperature':self.temperature,'max_tokens':self.max_tokens,'system':system,'input':payload,'total_tokens':None}
        self.calls.append(rec); start=time.perf_counter()
        try:
            if self.provider=='mock':
                result=respond(stage,payload); rec['total_tokens']=0
            else:
                messages=[{'role':'system','content':system},{'role':'user','content':json.dumps(payload)}]
                if self.provider=='ollama':
                    url=os.getenv('OLLAMA_BASE_URL','http://localhost:11434').rstrip('/')+'/api/chat'
                    body={'model':self.model,'messages':messages,'stream':False,'format':'json','options':{'temperature':self.temperature,'num_predict':self.max_tokens}}
                    headers={'Content-Type':'application/json'}
                else:
                    key=os.getenv('GEMINI_API_KEY','')
                    if not key: raise ValueError('GEMINI_API_KEY is not set')
                    url=os.getenv('GEMINI_BASE_URL','https://generativelanguage.googleapis.com/v1beta/openai').rstrip('/')+'/chat/completions'
                    body={'model':self.model,'messages':messages,'temperature':self.temperature,'max_tokens':self.max_tokens,'response_format':{'type':'json_object'}}
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+key}
                req=urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers)
                try:
                    with urllib.request.urlopen(req,timeout=float(os.getenv('REQUEST_TIMEOUT','120'))) as response: raw=json.load(response)
                except urllib.error.HTTPError as exc:
                    # Do not include request headers or credential-bearing bodies in logs.
                    raise RuntimeError(f'Model endpoint returned HTTP {exc.code}; check model name, quota, and credentials') from None
                if self.provider=='ollama':
                    content=raw['message']['content']
                    if 'prompt_eval_count' in raw and 'eval_count' in raw: rec['total_tokens']=raw['prompt_eval_count']+raw['eval_count']
                else:
                    content=raw['choices'][0]['message']['content']; rec['total_tokens']=raw.get('usage',{}).get('total_tokens')
                rec['raw_output']=content
                content=content.strip()
                if content.startswith('```'): content='\n'.join(content.splitlines()[1:-1])
                result=json.loads(content)
            if not isinstance(result,dict): raise ValueError('Model output must be an object')
            rec['output']=result; return result
        except Exception as exc:
            rec['error']=str(exc); raise
        finally: rec['latency_s']=time.perf_counter()-start
