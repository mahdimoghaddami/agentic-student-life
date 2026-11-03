"""Select failed fixed-context cases without overwriting any existing outputs."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--original',required=True)
p.add_argument('--outputs',required=True)
p.add_argument('--out',required=True)
a=p.parse_args()
def read(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()]
original=read(a.original);results=read(a.outputs)
ids={c['case_id'] for c in original}
if len(ids)!=len(original):raise SystemExit('Original cases have duplicate IDs')
if len({r['case_id'] for r in results})!=len(results):raise SystemExit('Output has duplicate IDs')
failed={r['case_id'] for r in results if r['status']!='ok'}
if not failed <= ids:raise SystemExit('Some failed IDs are absent from the original case file')
rows=[c for c in original if c['case_id'] in failed]
if any(c.get('episode_id') for c in rows):raise SystemExit('This helper is for fixed-context cases only; episodes require chronological replay')
if not rows:raise SystemExit('No failed cases to retry')
dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
with dest.open('x',encoding='utf-8') as f:
    for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
print(f'Saved {len(rows)} failed cases to {dest}; original outputs unchanged.')
