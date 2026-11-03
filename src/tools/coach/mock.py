# Deterministic fixtures exercise plumbing only. They are NOT LLM results.
def respond(stage,payload):
    if stage=='judge': return {'scores':{'context_awareness':3,'goal_alignment':3,'clarity':3},'rationale':'MOCK placeholder; not a valid judge rating.'}
    if stage=='review': return {'accept':True,'issues':[],'revision_request':''}
    if stage=='plan':
        if not payload.get('tool_results') and payload.get('tools'):
            return {'tool_calls':[{'name':'get_personal_baseline','arguments':{'days':7}}]}
        return {'evidence_ids':[],'information_gaps':[],'candidate_actions':['clarify','suggest','no_message'],'next_steps':['Choose one appropriate action'],'ready':True}
    ctx=payload['context']; p=ctx['profile']; h=ctx['history']
    if p.get('do_not_disturb'): return {'decision':'no_message','final_message':None,'evidence':[{'source':p.get('source','simulated_profile'),'detail':'Do not disturb preference.'}]}
    sleep=ctx['observations']['sleep']
    if sleep['missing']:
        return {'decision':'clarify','final_message':'Would a short break or help planning your next task be more useful right now?','evidence':[{'source':'missing_data','detail':'No recent sleep report is available.'}]}
    msg='Would you like to take a short, quiet break before your next task?'
    if p.get('preferred_activity')=='stretching': msg='Would a brief stretch at your desk fit your plans right now?'
    if any(e.get('kind')=='feedback' and e.get('value')=='rejected' for e in h): msg='Would you prefer help choosing one small next step for your work?'
    return {'decision':'suggest','final_message':msg,'evidence':[{'source':p.get('source','simulated_profile'),'detail':'Uses the current supplied coaching preferences.'}]}
