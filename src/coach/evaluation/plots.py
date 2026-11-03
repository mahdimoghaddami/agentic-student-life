from pathlib import Path
from ..io import read_json

def plot_comparison(run_root,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    files=sorted(Path(run_root).glob('*/report/metrics.json'))
    if not files: raise ValueError('Generate each run report first')
    rows=[(p.parent.parent.name,read_json(p)) for p in files]; out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for metric in ('success_rate','decision_appropriateness','mean_latency_s','mean_llm_calls','mean_tokens'):
        valid=[(name,r[metric]) for name,r in rows if r.get(metric) is not None]
        if not valid: continue
        fig,ax=plt.subplots(figsize=(9,5)); ax.barh([x[0] for x in valid],[x[1] for x in valid]);ax.set_xlabel(metric)
        ax.set_title(('MOCK plumbing check — ' if any(r.get('is_mock') for _,r in rows) else '')+metric)
        fig.tight_layout();fig.savefig(out/(metric+'.png'),dpi=160);plt.close(fig)
    for group in ('judge_means','human_llm_mae'):
        valid=[(name,r[group]) for name,r in rows if group in r]
        if not valid: continue
        fig,ax=plt.subplots(figsize=(10,5))
        dimensions=list(valid[0][1]); width=.8/len(dimensions)
        for i,d in enumerate(dimensions):ax.bar([j+i*width for j in range(len(valid))],[r[d] for _,r in valid],width,label=d)
        ax.set_xticks([j+.8/2-width/2 for j in range(len(valid))],[name for name,_ in valid],rotation=30,ha='right');ax.legend();ax.set_title(group);fig.tight_layout();fig.savefig(out/(group+'.png'),dpi=160);plt.close(fig)
