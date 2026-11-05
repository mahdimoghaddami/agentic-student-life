# Personalized Student Stress Coaching with Language Agents

The 18-page research paper covers the task, data processing, five-role architecture, tools, skills, memory, input/output contract, complete workflow, model settings, evaluation, required ablations, results, and limitations. Its appendices include structured examples, all output fields, pseudocode, the case manifest, the exact rubric, and requirement coverage.

- `studentlife_coach.pdf`: compiled paper.
- `studentlife_coach.tex`: paper source.
- `workflow.tex`: vector TikZ diagram with agent, processing, decision, storage, input/output, and human-rater shapes.
- `tables/`, `examples/`, `figures/`: supporting assets derived from saved experimental observations and scores.
- `evidence_manifest.json`: hashes identifying the source evidence used by the asset builder.

From the repository root:

```powershell
uv run python -B scripts/build_research_paper_assets.py
latexmk -pdf -interaction=nonstopmode -halt-on-error -cd output/pdf/studentlife_coach_paper/studentlife_coach.tex
```

These commands prepare local assets and compile the document. They make no LLM API calls. Building the PDF requires LaTeX/TikZ and `latexmk`; the bibliography and style dependencies are included.
