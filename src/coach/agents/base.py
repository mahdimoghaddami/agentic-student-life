from ..prompts import COMMON,UNIFIED
class Agent:
    def __init__(self,name,instruction,model,tools,config):
        self.name,self.instruction,self.model,self.tools,self.config=name,instruction,model,tools,config
    def run(self,stage,payload):
        payload=dict(payload,tools=self.tools.catalog(),agent=self.name,tool_results=[])
        system=UNIFIED if self.config.mode=='single' else COMMON+self.instruction
        payload['stage']=stage
        payload['retrieved_evidence']=[e for e in self.tools.events if e['type']=='tool']
        if self.config.mode=='single':
            payload['working_history']=[{'stage':c['stage'],'output':c.get('output')} for c in self.model.calls if 'output' in c]
        for turn in range(self.config.tool_turns+1):
            payload['tool_results']=list(payload['tool_results'])
            answer=self.model.ask(stage,system,payload)
            calls=answer.get('tool_calls')
            if not calls: return answer
            if turn==self.config.tool_turns: raise ValueError('Tool turn budget exhausted')
            if not isinstance(calls,list) or len(calls)>6: raise ValueError('Invalid tool request batch')
            new=[]
            for call in calls:
                try: result=self.tools.call(call['name'],call.get('arguments',{}))
                except (KeyError,ValueError,TypeError) as exc:
                    result={'error':str(exc)}
                    self.tools.events.append({'type':'tool_error','request':call,'error':str(exc)})
                new.append({'request':call,'result':result})
            payload=dict(payload,tool_results=payload['tool_results']+new)
        raise AssertionError('Unreachable')
