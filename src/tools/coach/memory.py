import sqlite3,json
from .io import epoch
class Memory:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS events (scope TEXT, participant TEXT, event_id TEXT, at REAL, payload TEXT, PRIMARY KEY(scope, participant,event_id))")
    def add(self,scope,participant,event):
        self.db.execute("INSERT OR REPLACE INTO events VALUES (?,?,?,?,?)",(scope,participant,event['id'],epoch(event['at']),json.dumps(event)))
        self.db.commit()
    def get(self,scope,participant,at):
        rows=self.db.execute("SELECT payload FROM events WHERE scope=? AND participant=? AND at<=? ORDER BY at,event_id",(scope,participant,epoch(at))).fetchall()
        return [json.loads(x[0]) for x in rows]
    def close(self): self.db.close()
def effective_profile(base,events,at):
    profile=dict(base)
    for event in sorted(events,key=lambda e:epoch(e['at'])):
        if epoch(event['at'])<=epoch(at) and event['kind']=='preference_update':
            profile.update(event['updates'])
    return profile
