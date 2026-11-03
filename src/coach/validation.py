def validate_draft(d):
    if d.get('decision') not in ('suggest','clarify','no_message'): raise ValueError('Invalid decision')
    m=d.get('final_message')
    if d['decision']=='no_message' and m is not None: raise ValueError('Silence requires null message')
    if d['decision']!='no_message' and (not isinstance(m,str) or not m.strip()): raise ValueError('Message required')
    if not isinstance(d.get('evidence'),list): raise ValueError('Evidence must be a list')
    for e in d['evidence']:
        if not isinstance(e,dict) or not isinstance(e.get('source'),str) or not isinstance(e.get('detail'),str): raise ValueError('Invalid evidence')
    return d

def validate_plan(p):
    for key in ('evidence_ids','information_gaps','candidate_actions','next_steps'):
        if not isinstance(p.get(key),list): raise ValueError('Invalid plan: '+key)
    if not isinstance(p.get('ready'),bool): raise ValueError('Plan ready must be boolean')
    return p

def validate_review(r):
    if not isinstance(r.get('accept'),bool) or not isinstance(r.get('issues'),list) or not isinstance(r.get('revision_request'),str): raise ValueError('Invalid review')
    return r
