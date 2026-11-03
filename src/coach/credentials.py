"""Select a named Gemini credential; never rotate silently on quota errors."""
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
