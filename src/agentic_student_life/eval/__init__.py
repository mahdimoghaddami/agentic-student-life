"""Evaluation, judging, metrics, plotting, and LaTeX table generation."""

from .human import compute_human_vs_llm, export_human_sheet
from .judge import judge_run
from .latex import generate_all_tables
from .metrics import compute_run_metrics
from .plots import generate_all_plots

__all__ = [
    "compute_human_vs_llm",
    "compute_run_metrics",
    "export_human_sheet",
    "generate_all_plots",
    "generate_all_tables",
    "judge_run",
]

