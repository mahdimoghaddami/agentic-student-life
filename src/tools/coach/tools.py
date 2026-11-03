from .data.features import summarize
SKILLS={
 'study_planning':{'source':'authored_skill','procedure':['Use recent reported coursework and study conditions.','Distinguish today from older due-date responses.','Offer one manageable study step consistent with preferences.']},
 'sleep_routine':{'source':'authored_skill','procedure':['Use decoded sleep duration, quality and daytime sleepiness.','Do not infer sleep from darkness, charging or phone lock.','Offer an optional routine adjustment without medical claims.']},
 'movement_break':{'source':'authored_skill','procedure':['Consider recent self-reported exercise and sampled movement.','Missing samples do not prove inactivity.','Respect mobility constraints and rejected suggestions.']},
 'manageable_break':{'source':'authored_skill','procedure':['Check preferences and recent rejected advice.','Offer one optional manageable break.','Avoid promising stress reduction.']},
 'clarify_missing':{'source':'authored_skill','procedure':['Identify the missing fact that would change the decision.','Ask one short question.','Do not interpret absent sensing as inactivity.']},
 'adapt_feedback':{'source':'authored_skill','procedure':['Use latest explicit preference.','Avoid repeating a rejected action.','Offer an alternative or remain silent.']},
 'campus_resource':{'source':'authored_skill','procedure':['Retrieve catalog entry.','Preserve its simulated label.','Never invent contact information.']}}
RESOURCES=[{'id':'demo_learning_support','source':'simulated_resource','name':'Simulated campus learning support','description':'Illustrative study-planning support; no real contact information.'}]
class Tools:
    def __init__(self,records,case,context,config,events):
        self.records,self.case,self.context,self.config,self.events=records,case,context,config,events
    def catalog(self):
        if not self.config.tools: return {}
        d={'get_recent_observations':{'days':'integer 1..30'},'get_personal_baseline':{'days':'integer 1..30'},'get_preferences':{},'get_interaction_history':{},'lookup_resource':{}}
        if 'extended_observations' in self.context: d['get_extended_observations']={'section':['all','ema','sensing','optional']}
        if self.config.skills: d['get_coaching_skill']={'name':list(SKILLS)}
        return d
    def call(self,name,args):
        if name not in self.catalog(): raise ValueError('Tool unavailable')
        if name in ('get_recent_observations','get_personal_baseline'):
            days=args.get('days',7)
            if not isinstance(days,int) or not 1<=days<=30: raise ValueError('days must be 1..30')
            result=summarize(self.records,self.case['participant_id'],self.case['decision_time'],days)
            if 'extended_observations' in self.context:
                result={'original_streams':result,'extended_observations':self.context['extended_observations'],
                        'note':'Original streams use requested days; extended context retains its frozen provenance.windows. Do not treat an absent original stream as missing extended evidence.'}
        elif name=='get_extended_observations':
            section=args.get('section','all')
            if section not in ('all','ema','sensing','optional'): raise ValueError('Unknown context section')
            extended=self.context['extended_observations']
            result=extended if section=='all' else extended['observations'].get(section,{'missing':True})
        elif name=='get_preferences': result=self.context['profile']
        elif name=='get_interaction_history': result=self.context['history']
        elif name=='get_coaching_skill': result=SKILLS[args['name']]
        else: result=RESOURCES
        self.events.append({'type':'tool','name':name,'arguments':args,'result':result})
        return result
