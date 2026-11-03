"""Select a named Gemini credential or discover the opt-in automatic pool."""
import os,re

def configured_secrets():
    return [v.strip() for k,v in os.environ.items()
            if re.fullmatch(r'GEMINI_API_KEY(?:_[1-9][0-9]*)?',k) and v.strip()]

def gemini_credential():
    slot=os.getenv('GEMINI_KEY_SLOT','').strip()
    if slot:
        if not re.fullmatch(r'[1-9][0-9]*',slot):
            raise ValueError('GEMINI_KEY_SLOT must be a positive integer')
        name='GEMINI_API_KEY_'+slot
    else:
        name='GEMINI_API_KEY'
    value=os.getenv(name,'').strip()
    if not value:
        raise ValueError(f'{name} is not set; enter the selected key in your local .env')
    return name,value

def gemini_pool():
    """Numerically ordered, deduplicated authorized keys; values never enter logs."""
    import hashlib
    names=sorted((k for k in os.environ if re.fullmatch(r'GEMINI_API_KEY_[1-9][0-9]*',k)),key=lambda k:int(k.rsplit('_',1)[1]))
    if os.getenv('GEMINI_API_KEY','').strip():names.append('GEMINI_API_KEY')
    seen=set();pool=[]
    for name in names:
        secret=os.getenv(name,'').strip()
        if not secret or secret in seen:continue
        seen.add(secret)
        fingerprint=hashlib.sha256(secret.encode()).hexdigest()
        suffix=name.removeprefix('GEMINI_API_KEY')
        project=os.getenv('GEMINI_PROJECT_ID'+suffix,'').strip()
        group='project:'+project if project else 'key:'+fingerprint
        pool.append((name,secret,fingerprint,group))
    if not pool:raise ValueError('Auto mode needs GEMINI_API_KEY or numbered GEMINI_API_KEY_N entries')
    return pool
