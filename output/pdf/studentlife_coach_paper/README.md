# Personalized Student Stress Coaching with Language Agents

The paper has 10 main-text pages, one reference page, and three appendix pages (14 pages total). Its six main sections are Introduction, Background and Related Works, Methodology, Evaluation, Ablation study, and Individual contributions. It covers the task, data processing, five-role architecture, tools, skills, memory, input/output contract, workflow, model settings, evaluation, ablations, results, and limitations. The appendices retain a structured example and complete output schema, the case manifest, component controls, and the exact evaluation rubric. Implementation and reproduction instructions are documented in the repository README.

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
