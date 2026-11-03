"""CLI: build a structured agent context for one or multiple evaluation cases."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .builder import build_student_context,coaching_signals


def main():
    p=argparse.ArgumentParser(description='Build time-safe StudentLife agent observations')
    p.add_argument('--dataset',default='dataset')
    p.add_argument('--participant')
    p.add_argument('--decision-time')
    p.add_argument('--cases',help='Input JSONL with participant_id and decision_time')
    p.add_argument('--out',default='outputs/student_contexts.jsonl')
    p.add_argument('--include',default='ema,sensing,optional',help='Comma-separated: ema,sensing,optional')
    p.add_argument('--exclude-ema',default='',help='Comma-separated exact survey names, for ablations')
    p.add_argument('--exclude-sensing',default='',help='Comma-separated sensor substreams')
    p.add_argument('--sensing-streams',default='activity,conversation,phonelock,phonecharge,dark',
                   help='Comma-separated selected sensing streams; add audio,gps,wifi,... as needed')
    p.add_argument('--ema-days',type=float,default=7)
    p.add_argument('--assume-syllabus-known',action='store_true',
                   help='Use education/deadlines.csv as an assumed pre-known schedule (simulation only)')
    p.add_argument('--sensing-hours',type=float,default=24)
    args=p.parse_args()
    if not args.cases and not (args.participant and args.decision_time):
        p.error('Provide --cases or both --participant and --decision-time')
    from .ema import FIELDS
    from .sensing import PASSIVE_STREAMS
    enabled_ema=set(FIELDS)-set(x.strip() for x in args.exclude_ema.split(',') if x.strip())
    enabled_sensing=set(x.strip() for x in args.sensing_streams.split(',') if x.strip())-set(x.strip() for x in args.exclude_sensing.split(',') if x.strip())
    unknown=enabled_sensing-set(PASSIVE_STREAMS)
    if unknown:p.error(f'Unknown sensing streams: {sorted(unknown)}')
    if args.cases:
        with open(args.cases,encoding='utf-8') as f:
            cases=[json.loads(line) for line in f if line.strip()]
    else: cases=[{'case_id':'case_001','participant_id':args.participant,'decision_time':args.decision_time}]
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():p.error('Output already exists; choose a new context file to preserve reproducibility')
    failures=0
    with out.open('w',encoding='utf-8') as f:
        for i,case in enumerate(cases,1):
            try:
                context=build_student_context(args.dataset,case['participant_id'],case['decision_time'],
                    include=[x.strip() for x in args.include.split(',') if x.strip()],
                    ema_surveys=enabled_ema,sensing_streams=enabled_sensing,
                    ema_days=args.ema_days,sensing_hours=args.sensing_hours,
                    assume_syllabus_known=args.assume_syllabus_known)
                context['schema_version']='studentlife-context-v2'
                context['case_id']=case.get('case_id',f'case_{i:03d}')
                context['coaching_signals']=coaching_signals(context)
                # Preserve simulated user-specific context distinctly from observations.
                for name in ('profile','interaction_history','student_goals','preferences'):
                    if name in case:
                        context.setdefault('simulated_user_context',{})[name]=case[name]
                if 'simulated_user_context' in context:
                    context['simulated_user_context']['provenance']='SIMULATED case input; not an observation from StudentLife'
                context['status']='ok'
            except (OSError,ValueError,KeyError,TypeError) as exc:
                failures+=1
                context={'case_id':case.get('case_id',f'case_{i:03d}'),
                         'participant_id':case.get('participant_id'),
                         'status':'error','error':f'{type(exc).__name__}: {exc}'}
            f.write(json.dumps(context,ensure_ascii=False)+'\n')
    import hashlib
    definition=Path(args.dataset)/'EMA/EMA_definition.json'
    manifest={'arguments':vars(args),'codebook_sha256':hashlib.sha256(definition.read_bytes()).hexdigest(),
              'contexts_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
              'cases_sha256':hashlib.sha256(Path(args.cases).read_bytes()).hexdigest() if args.cases else None,
              'note':'Contexts are frozen per case. Retain this file for identical evidence across ablations.'}
    Path(str(out)+'.manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Wrote {len(cases)} cases to {out}; failures={failures}')
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
