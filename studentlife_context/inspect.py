"""Inspect available column names and participant coverage; never print raw values."""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path
from .common import read_records,participant_files


def inventory(root,participant):
    out={}
    for folder in sorted(p for p in Path(root).rglob('*') if p.is_dir()):
        if folder.name=='response': continue
        files=list(participant_files(folder,participant))
        files=[x for x in files if x.parent==folder]
        if not files:continue
        columns=set(); rows=0
        for f in files:
            for rec in read_records(f):
                rows+=1; columns.update(rec.keys())
        out[str(folder.relative_to(root))]={'files':len(files),'rows':rows,
                                           'fields':sorted(columns)}
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dataset',default='dataset')
    p.add_argument('--participant',default='u00')
    p.add_argument('--out',default='outputs/studentlife_schema_u00.json')
    a=p.parse_args()
    result=inventory(Path(a.dataset),a.participant)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Wrote field-name/row-count inventory:',path)
    print('Categories:',len(result))


if __name__=='__main__':main()
