"""Generate booktabs LaTeX tables directly into `report/tables/`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .plots import CONFIG_LABELS

CAT_NAMES = {
    "typical_high_stress": "Typical: High Stress / Load",
    "typical_doing_fine": "Typical: Doing Fine",
    "missing_data": "Missing Data (Natural + Masked)",
    "preference_update": "Preference Updates (Multi-Step)",
    "safety_or_restraint": r"Safety \& Restraint",
}


def generate_all_tables(
    all_metrics: dict[str, dict[str, Any]],
    human_vs_llm: dict[str, Any],
    table_dir: str | Path = "report/tables",
) -> list[str]:
    """Write `table1_main_results.tex`, `table2_ablations.tex`, and `table3_human_vs_llm.tex`."""
    tdir = Path(table_dir)
    tdir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    ref = all_metrics.get("full") or next((v for v in all_metrics.values() if v.get("available")), None)
    if ref and ref.get("available"):
        t1_lines = [
            r"\begin{tabular}{lccccccc}",
            r"\toprule",
            r"Category & $N$ & Dec.\ Acc.\ (\%) & Context & Goal Align. & Clarity & Latency (s) & Tokens \\",
            r"\midrule",
        ]
        by_cat = ref.get("by_category", {})
        for cat_key, cat_label in CAT_NAMES.items():
            if cat_key not in by_cat:
                continue
            cm = by_cat[cat_key]
            ca_s = f"{cm['context_awareness']:.2f}" if cm["n_scored_messages"] else "---"
            ga_s = f"{cm['goal_alignment']:.2f}" if cm["n_scored_messages"] else "---"
            cl_s = f"{cm['clarity']:.2f}" if cm["n_scored_messages"] else "---"
            t1_lines.append(
                f"{cat_label} & {cm['n_cases']} & {cm['decision_acc']:.1f} & "
                f"{ca_s} & {ga_s} & {cl_s} & {cm['latency_mean']:.1f} & {int(cm['tokens_mean'])} \\\\"
            )
        ref_lbl = CONFIG_LABELS.get(ref["config_id"], ref["config_id"])
        t1_lines.extend([
            r"\midrule",
            f"\\textbf{{Overall ({ref_lbl})}} & "
            f"\\textbf{{{ref['n_cases']}}} & \\textbf{{{ref['decision_acc']:.1f}}} & "
            f"\\textbf{{{ref['context_awareness']['mean']:.2f}}} & "
            f"\\textbf{{{ref['goal_alignment']['mean']:.2f}}} & "
            f"\\textbf{{{ref['clarity']['mean']:.2f}}} & "
            f"\\textbf{{{ref['latency_s']['mean']:.1f}}} & "
            f"\\textbf{{{int(ref['total_tokens']['mean'])}}} \\\\",
            r"\bottomrule",
            r"\end{tabular}",
        ])
        p1 = tdir / "table1_main_results.tex"
        p1.write_text("\n".join(t1_lines) + "\n", encoding="utf-8")
        saved.append(str(p1))

    # Table 2: Ablation study table
    t2_lines = [
        r"\begin{tabular}{lccccccccc}",
        r"\toprule",
        r"Configuration & Succ.\ (\%) & Dec.\ Acc.\ & Pref.\ Adh.\ & Context & Goal & Clarity & Mean & Calls & Tokens \\",
        r"\midrule",
    ]
    for cid, label in CONFIG_LABELS.items():
        m = all_metrics.get(cid)
        if not m or not m.get("available"):
            continue
        bold = cid == "full"
        fmt = (lambda s: f"\\textbf{{{s}}}") if bold else (lambda s: s)
        s_succ = f"{m['success_rate']:.0f}"
        s_dacc = f"{m['decision_acc']:.1f}\\%"
        s_padh = f"{m['pref_adherence_rate']:.0f}\\%"
        s_ca = f"{m['context_awareness']['mean']:.2f}"
        s_ga = f"{m['goal_alignment']['mean']:.2f}"
        s_cl = f"{m['clarity']['mean']:.2f}"
        s_jm = f"{m['judge_mean']['mean']:.2f}"
        s_calls = f"{m['llm_calls']['mean']:.1f}"
        s_toks = f"{int(m['total_tokens']['mean'])}"
        t2_lines.append(
            f"{fmt(label)} & {fmt(s_succ)} & {fmt(s_dacc)} & {fmt(s_padh)} & "
            f"{fmt(s_ca)} & {fmt(s_ga)} & {fmt(s_cl)} & {fmt(s_jm)} & "
            f"{fmt(s_calls)} & {fmt(s_toks)} \\\\"
        )
    t2_lines.extend([r"\bottomrule", r"\end{tabular}"])
    p2 = tdir / "table2_ablations.tex"
    p2.write_text("\n".join(t2_lines) + "\n", encoding="utf-8")
    saved.append(str(p2))

    # Table 3: Human Judge vs LLM Judge
    if human_vs_llm.get("available"):
        bc = human_vs_llm["by_criterion"]
        crit_labels = [
            ("context_awareness", "Context Awareness (1--5)"),
            ("goal_alignment", "Goal Alignment (1--5)"),
            ("clarity", "Clarity \\& Tone (1--5)"),
            ("mean", "Overall Mean Score (1--5)"),
        ]
        t3_lines = [
            r"\begin{tabular}{lccccc}",
            r"\toprule",
            r"Criterion & Human ($\mu \pm \sigma$) & LLM Judge ($\mu \pm \sigma$) & MAD $|H - L|$ & $\Delta (L - H)$ & Within $\pm 1.0$ (\%) \\",
            r"\midrule",
        ]
        for ckey, clbl in crit_labels:
            row = bc[ckey]
            t3_lines.append(
                f"{clbl} & ${row['human_mean']:.2f} \\pm {row['human_std']:.2f}$ & "
                f"${row['llm_mean']:.2f} \\pm {row['llm_std']:.2f}$ & "
                f"\\textbf{{{row['mad']:.2f}}} & "
                f"${row['signed_diff_llm_minus_human']:+.2f}$ & "
                f"{row['within_1pt_rate'] * 100:.0f}\\% \\\\"
            )
        t3_lines.extend([r"\bottomrule", r"\end{tabular}"])
        p3 = tdir / "table3_human_vs_llm.tex"
        p3.write_text("\n".join(t3_lines) + "\n", encoding="utf-8")
        saved.append(str(p3))

    return saved
