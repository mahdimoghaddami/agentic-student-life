import time
from .agents.planner import Planner
from .agents.coach import Coach
from .agents.reviewer import Reviewer
from .models import Model
from .tools import Tools
from .memory import effective_profile
from .data.features import summarize
from .validation import validate_draft,validate_plan,validate_review
from .io import epoch
from .data.grounding import grounding_issues

def run_case(case,records,config,memory,scope,extended_context=None):
    start=time.perf_counter(); events=[]; model=None; context={}; rounds=cycles=0; review_status="not_reviewed"
    out={k:case[k] for k in ('case_id','participant_id','decision_time')}
    out.update(config_id=config.name,status='failed',decision=None,final_message=None,evidence=[],error=None)
    try:
        for e in case.get('history',[]):
            if config.memory and epoch(e['at'])<=epoch(case['decision_time']): memory.add(scope,case['participant_id'],e)
        history=memory.get(scope,case['participant_id'],case['decision_time']) if config.memory else []
        profile=effective_profile(case['profile'],history,case['decision_time'])
        context={'participant_id':case['participant_id'],'decision_time':case['decision_time'],'profile':profile,'history':history,'observations':summarize(records,case['participant_id'],case['decision_time'])}
        if extended_context is not None: context['extended_observations']=extended_context
        model=Model(config.provider,config.model,config.temperature,config.max_tokens)
        out.update(model=model.model,provider=model.provider,is_mock=model.provider=='mock')
        tools=Tools(records,case,context,config,events)
        planner,coach,reviewer=Planner(model,tools,config),Coach(model,tools,config),Reviewer(model,tools,config)
        plan=None
        for _ in range(config.planning_rounds):
            plan=validate_plan(planner.run('plan',{'context':context,'previous_plan':plan})); rounds+=1
            events.append({'type':'plan','round':rounds,'plan':plan})
            if plan['ready']: break
        draft=validate_draft(coach.run('draft',{'context':context,'plan':plan}))
        for _ in range(config.reflection_cycles):
            issues=grounding_issues(draft,context)
            review=validate_review(reviewer.run('review',{'context':context,'plan':plan,'draft':draft,'grounding_issues':issues})); cycles+=1
            model_review=dict(review)
            if issues:
                review=dict(review,accept=False,issues=list(review['issues'])+issues,revision_request=review['revision_request']+' Fix the supplied grounding issues.')
            events.append({'type':'review','cycle':cycles,'review':review,'model_review':model_review,'deterministic_issues':issues})
            if review['accept']:
                review_status='accepted'; break
            review_status='revised_without_further_review'
            draft=validate_draft(coach.run('revise',{'context':context,'plan':plan,'draft':draft,'review':review}))
        issues=grounding_issues(draft,context)
        events.append({'type':'grounding_check','issues':issues,'draft':draft})
        if issues: raise ValueError('Grounding validation failed: '+'; '.join(issues))
        out.update(draft,status='ok')
        if config.memory:
            memory.add(scope,case['participant_id'],{'id':'generated_'+case['case_id'],'at':case['decision_time'],'kind':'coach_output','source':'generated_coach','decision':draft['decision'],'message':draft['final_message']})
    except Exception as exc: out['error']=f'{type(exc).__name__}: {exc}'
    calls=model.calls if model else []
    tokens=[c['total_tokens'] for c in calls]
    out['trace']={'llm_calls':len(calls),'total_tokens':sum(tokens) if all(t is not None for t in tokens) else None,'token_usage_complete':all(t is not None for t in tokens),'latency_s':time.perf_counter()-start,'planning_rounds':rounds,'reflection_cycles':cycles,'final_review_status':review_status}
    # Include tool-derived evidence for evaluation, but never expose expected decisions to agents.
    out['evaluation_context']=dict(context,tool_results=[e for e in events if e['type']=='tool'])
    out['acceptable_decisions']=case.get('acceptable_decisions',[])
    return out,{'case_id':case['case_id'],'events':events,'model_calls':calls}
