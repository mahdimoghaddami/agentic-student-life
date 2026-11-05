"""Prepare factual Typst slide data from saved results, without model calls."""
import csv
import json
import hashlib
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / 'runs_corrected/2026-11-04_v3'
LABELS = {'full':'Full', 'single':'Single coach', 'no_plan':'No planning', 'no_refl':'No reflection',
          'plan1':'Planning max. 1', 'plan3':'Planning max. 3', 'refl1':'Reflection max. 1',
          'refl3':'Reflection max. 3', 'modelB':'Model B'}
ORDER = ['full','single','no_plan','no_refl','plan1','plan3','refl1','refl3','modelB']


def export_report_figures():
    """Keep the report artwork as vectors; crop only at the SVG viewport."""
    paper = ROOT / 'output/pdf/studentlife_coach_paper'
    assets = ROOT / 'presentation/assets'
    sources = {}
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        specifications = [
            ('report-depth-tradeoffs.svg', paper / 'figures/depth_tradeoffs.pdf', 1, None, 'Figure 2'),
            ('report-workflow-planning.svg', paper / 'studentlife_coach.pdf', 3,
             (55, 70, 490, 165), 'Figure 1, context and planning excerpt'),
            ('report-workflow-evaluation.svg', paper / 'studentlife_coach.pdf', 3,
             (155, 515, 390, 181), 'Figure 1, evaluation excerpt'),
        ]
        for name, source, page, crop, figure in specifications:
            raw = temporary / name
            subprocess.run(['pdftocairo', '-f', str(page), '-l', str(page), '-svg',
                            str(source), str(raw)], check=True, capture_output=True)
            tree = ET.parse(raw)
            svg = tree.getroot()
            if crop:
                x, y, width, height = crop
                svg.set('viewBox', f'{x} {y} {width} {height}')
                svg.set('width', f'{width}pt')
                svg.set('height', f'{height}pt')
            tree.write(assets / name, encoding='utf-8', xml_declaration=True)
            sources[name] = dict(source=source.relative_to(ROOT).as_posix(), page=page,
                                 figure=figure, crop_pdf_points=crop,
                                 sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    (assets / 'report_figure_sources.json').write_text(json.dumps(sources, indent=2)+'\n',encoding='utf-8')


def main():
    with (SUITE / 'comparison.csv').open(newline='',encoding='utf-8') as f:
        raw={row['config']:row for row in csv.DictReader(f)}
    rows=[]
    for name in ORDER:
        r=raw[name]
        rows.append(dict(id=name,label=LABELS[name],cases=int(r['cases']),
                         agreement=float(r['decision_accuracy_pct']),
                         matched=int(round(float(r['decision_accuracy_pct'])*int(r['cases'])/100)),
                         messages=int(r['messages_judged']),quality=float(r['quality_mean']),
                         calls=float(r['calls_mean']),tokens=float(r['tokens_mean']),
                         latency=float(r['latency_mean_s'])))
    outputs={r['case_id']:r for r in map(json.loads,(SUITE/'full/outputs.jsonl').read_text().splitlines())}
    summary=json.loads((SUITE/'summary_metrics.json').read_text())
    example=outputs['case_015']
    data=dict(rows=rows, human=summary['human_vs_llm']['by_criterion'],
              criterion_mad=summary['human_vs_llm']['all_criterion_ratings_mad'],
              example=dict(message=example['final_message'],words=len(example['final_message'].split()),
                           record={k:example[k] for k in ['case_id','participant_id','decision','skill_used','planning']},
                           trace={k:example['trace'][k] for k in ['llm_calls','total_tokens','latency_s']}),
              sources=['runs_corrected/2026-11-04_v3/comparison.csv',
                       'runs_corrected/2026-11-04_v3/summary_metrics.json',
                       'runs_corrected/2026-11-04_v3/full/outputs.jsonl'])
    target=ROOT/'presentation/assets/project_results.json'
    target.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    export_report_figures()
    print('Presentation data and vector report figures saved; no model calls.')


if __name__=='__main__':
    main()
