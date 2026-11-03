import argparse,os,json,hashlib
from pathlib import Path
from .io import load_env,read_json,read_jsonl,write_json,write_jsonl
from .config import load_config

def main():
    load_env();p=argparse.ArgumentParser(description='StudentLife multi-agent coach');s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('inspect');a.add_argument('--root',required=True);a.add_argument('--out',default='dataset_inspection.json')
    a=s.add_parser('import-data');a.add_argument('--root',required=True);a.add_argument('--mapping',required=True);a.add_argument('--out',required=True)
    a=s.add_parser('build-cases');a.add_argument('--observations',required=True);a.add_argument('--profiles',required=True);a.add_argument('--out',required=True);a.add_argument('--limit',type=int,default=100)
    for name in ('run','ablations'):
        a=s.add_parser(name);a.add_argument('--cases',default='examples/cases.jsonl');a.add_argument('--observations',help='Normalized observation JSONL; optional when --contexts is supplied');a.add_argument('--config',default='configs/full.json');a.add_argument('--out',required=True)
        a.add_argument('--contexts',help='Prepared StudentLife context JSONL shared across all configurations')
        if name=='run':a.add_argument('--episodes',action='store_true')
        else:
            a.add_argument('--model-b-provider',default=os.getenv('MODEL_B_PROVIDER','gemini'));a.add_argument('--model-b',default=os.getenv('MODEL_B',''));a.add_argument('--repeats',type=int,default=1)
    a=s.add_parser('judge');a.add_argument('--outputs',required=True);a.add_argument('--out',required=True);a.add_argument('--provider',default=os.getenv('JUDGE_PROVIDER','gemini'));a.add_argument('--model',default=os.getenv('JUDGE_MODEL',''));a.add_argument('--allow-mock',action='store_true')
    a=s.add_parser('human-export');a.add_argument('--outputs',required=True);a.add_argument('--out',required=True);a.add_argument('--n',type=int,default=10);a.add_argument('--seed',type=int,default=42)
    a=s.add_parser('report');a.add_argument('--outputs',required=True);a.add_argument('--out',required=True);a.add_argument('--judge');a.add_argument('--human');a.add_argument('--mapping')
    a=s.add_parser('plots');a.add_argument('--runs',required=True);a.add_argument('--out',required=True)
    a=s.add_parser('evaluate-study');a.add_argument('--runs',required=True);a.add_argument('--score',action='store_true');a.add_argument('--provider',default=os.getenv('JUDGE_PROVIDER','gemini'));a.add_argument('--model',default=os.getenv('JUDGE_MODEL',''));a.add_argument('--allow-mock',action='store_true')
    args=p.parse_args()
    if args.cmd in ('run','ablations') and args.observations is None and args.contexts is None:
        args.observations='examples/observations.jsonl'
    if args.cmd=='inspect':
        from .data.importer import inspect_dataset
        result=inspect_dataset(args.root);definition=Path(args.root)/'EMA/EMA_definition.json'
        result['ema_definition_sha256']=hashlib.sha256(definition.read_bytes()).hexdigest() if definition.exists() else None
        write_json(args.out,result);print('Saved inspection:',args.out)
    elif args.cmd=='import-data':
        from .data.importer import import_dataset
        print(import_dataset(args.root,args.mapping,args.out))
    elif args.cmd=='build-cases':
        from .data.cases import build_cases
        rows=build_cases(read_jsonl(args.observations),read_json(args.profiles),limit=args.limit);write_jsonl(args.out,rows);print('Cases:',len(rows))
    elif args.cmd=='run':
        from .runner import run
        result=run(args.cases,args.observations,load_config(args.config),args.out,args.episodes,contexts_path=args.contexts)
        if result['failed']: raise SystemExit(1)
    elif args.cmd=='ablations':
        from .ablations import run_ablations
        run_ablations(args.cases,args.observations,load_config(args.config),args.out,args.model_b_provider,args.model_b,args.repeats,contexts_path=args.contexts)
    elif args.cmd=='judge':
        from .evaluation.judge import judge
        result=judge(args.outputs,args.out,args.provider,args.model,args.allow_mock)
        if any(r['status']=='failed' for r in result):raise SystemExit(1)
    elif args.cmd=='human-export':
        from .evaluation.human import export_ratings
        export_ratings(args.outputs,args.out,args.n,args.seed)
    elif args.cmd=='report':
        from .evaluation.metrics import report
        print(json.dumps(report(args.outputs,args.out,args.judge,args.human,args.mapping),indent=2))
    elif args.cmd=='evaluate-study':
        from .evaluation.study import evaluate_study
        evaluate_study(args.runs,args.provider,args.model,args.score,args.allow_mock)
    else:
        from .evaluation.plots import plot_comparison
        plot_comparison(args.runs,args.out)
if __name__=='__main__': main()
