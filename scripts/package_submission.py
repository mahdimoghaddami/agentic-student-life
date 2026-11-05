"""Build the minimal assignment submission from an explicit allowlist."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'submission/moghaddami_piggott.zip'
PREFIX = 'agentic-student-life'
RUNS = ['full', 'single', 'no_refl', 'no_plan', 'refl1', 'refl3', 'plan1', 'plan3', 'modelB']


def submission_files():
    names = {'.env.example', '.python-version', 'README.md', 'pyproject.toml', 'uv.lock',
             'configs/full.toml', 'configs/ablations.toml', 'configs/judge.toml',
             'configs/evaluation.toml', 'configs/2026-11-04/full-paid.toml',
             'configs/2026-11-04/judge.toml', 'scripts/judge_corrected.py',
             'scripts/analyze_corrected.py',
             'output/pdf/studentlife_coach_paper/studentlife_coach.pdf'}
    for folder, suffix in [('src', '.py'), ('tests', '.py'), ('prompts', '.md'),
                           ('skills', '.md'), ('resources', '.json')]:
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob('*')
                     if p.is_file() and p.suffix == suffix and '__pycache__' not in p.parts)
    names.update('cases/' + name for name in ['cases.jsonl', 'profiles.json', 'feedback_scripts.json', 'selection.md'])
    names.update(f'configs/2026-11-04/{name}.toml' for name in RUNS if name != 'full')
    suite = 'runs_corrected/2026-11-04_v3/'
    names.update(suite + name for name in ['summary_metrics.json', 'matched_comparisons.json', 'comparison.csv',
                 'preference_proxy_review.json', 'baseline_preservation_sha256.json', 'judge_api_usage.jsonl'])
    names.update(suite + 'inputs/' + name for name in ['cases.jsonl', 'profiles.json', 'feedback_scripts.json'])
    for run in RUNS:
        names.update(suite + run + '/' + name for name in ['outputs.jsonl', 'calls.jsonl', 'run.log',
                     'failed_cases.json', 'config.snapshot.toml', 'manifest.json', 'api_usage.jsonl', 'judge_scores.jsonl'])
    names.update(suite + 'full/human_eval/' + name for name in ['human_ratings.json', 'blind_rating_sheet.html'])
    names.update(suite + 'plan3/' + name for name in ['recovery_info.json', 'attempt1_outputs.jsonl', 'attempt1_failed_cases.json'])
    return sorted(names)


def main():
    names = submission_files()
    for name in names:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(name)
        if Path(name).parts[0] in {'.git', '.venv', 'data', 'cache', 'tmp'} or '__pycache__' in Path(name).parts:
            raise ValueError(f'Excluded path: {name}')
        if path.name == '.env' or path.suffix in {'.pyc', '.parquet', '.safetensors', '.pt', '.pth'}:
            raise ValueError(f'Excluded file: {name}')
        if re.search(rb'AIza[0-9A-Za-z_-]{30,}|\bsk-[0-9A-Za-z_-]{25,}', path.read_bytes()):
            raise ValueError(f'Possible API credential in {name}')
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    temporary = DESTINATION.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in names:
            archive.write(ROOT / name, PREFIX + '/' + name)
    with zipfile.ZipFile(temporary) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(names)
        for name in names:
            assert archive.read(PREFIX + '/' + name) == (ROOT / name).read_bytes(), name
        suite = PREFIX + '/runs_corrected/2026-11-04_v3/'
        total_outputs = total_scores = 0
        for run in RUNS:
            records = [json.loads(line) for line in archive.read(suite + run + '/outputs.jsonl').splitlines()]
            assert len(records) == 20 and all(r['status'] == 'ok' for r in records), run
            scores = [json.loads(line) for line in archive.read(suite + run + '/judge_scores.jsonl').splitlines()]
            assert {r['case_id'] for r in scores} == {r['case_id'] for r in records if r['final_message']}, run
            total_outputs += len(records)
            total_scores += len(scores)
        assert total_outputs == 180 and total_scores == 140
        assert len(json.loads(archive.read(suite + 'full/human_eval/human_ratings.json'))) == 10
    temporary.replace(DESTINATION)
    print(f'{DESTINATION.relative_to(ROOT)}: {len(names)} files, {DESTINATION.stat().st_size:,} bytes')
    print('SHA256:', hashlib.sha256(DESTINATION.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
