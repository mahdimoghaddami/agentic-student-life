"""Prepare research-paper tables/examples from saved observations and scores. No API calls."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "runs_corrected/2026-11-04_v3"
PAPER = ROOT / "output/pdf/studentlife_coach_paper"
ORDER = ["full", "single", "no_plan", "plan1", "plan3", "no_refl", "refl1", "refl3", "modelB"]
LABELS = {"full": "Full", "single": "Single coach", "no_plan": "No planning", "plan1": "Planning max. 1",
          "plan3": "Planning max. 3", "no_refl": "No reflection", "refl1": "Reflection max. 1",
          "refl3": "Reflection max. 3", "modelB": "Model B"}


def tex(text):
    mapping = {"\\": r"\textbackslash{}", "_": r"\_", "&": r"\&", "%": r"\%", "#": r"\#",
               "{": r"\{", "}": r"\}", ">": r"\textgreater{}", "<": r"\textless{}"}
    return "".join(mapping.get(c, c) for c in str(text))


def table(name, columns, header, rows):
    text = [r"\begin{tabular}{" + columns + "}", r"\toprule", header + r" \\", r"\midrule"]
    text += [" & ".join(row) + r" \\" for row in rows]
    text += [r"\bottomrule", r"\end{tabular}"]
    (PAPER / "tables" / f"{name}.tex").write_text("\n".join(text) + "\n")


def format_rubric(markdown):
    """Preserve prompt words while typesetting Markdown as readable paper text."""
    def inline(line):
        parts = re.split(r"(\*\*.*?\*\*|`.*?`)", line)
        return "".join(r"\textbf{" + tex(p[2:-2]) + "}" if p.startswith("**")
                       else r"\texttt{" + tex(p[1:-1]) + "}" if p.startswith("`")
                       else tex(p) for p in parts)
    output, items = [r"\begingroup\small"], False
    for line in markdown.splitlines():
        if not line.strip():
            continue
        if not line.startswith("- ") and items:
            output.append(r"\end{itemize}"); items = False
        if line.startswith("### "):
            output.append(r"\subsubsection*{" + inline(line[4:]) + "}")
        elif line.startswith("## "):
            output.append(r"\subsection*{" + inline(line[3:]) + "}")
        elif line.startswith("# "):
            output.append(r"\noindent\textbf{" + inline(line[2:]) + r"}\par\smallskip")
        elif line.startswith("- "):
            if not items:
                output.append(r"\begin{itemize}\setlength{\itemsep}{1pt}\setlength{\parskip}{0pt}"); items = True
            output.append(r"\item " + inline(line[2:]))
        else:
            output.append(r"\noindent " + inline(line) + r"\par\smallskip")
    if items:
        output.append(r"\end{itemize}")
    return "\n".join(output + [r"\endgroup"]) + "\n"


def figures(metrics, paired):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    short = {"full": "Full", "single": "SA", "no_plan": "P0", "plan1": "P1", "plan3": "P3",
             "no_refl": "R0", "refl1": "R1", "refl3": "R3", "modelB": "B"}
    with plt.rc_context({"font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
                         "xtick.labelsize": 7, "ytick.labelsize": 7, "pdf.fonttype": 42}):
        names = ORDER[1:]
        delta = [paired[n]["paired_quality_difference_variant_minus_full"] for n in names]
        fig, ax = plt.subplots(figsize=(3.4, 2.65))
        ax.barh([short[n] for n in names], delta,
                color=["#087f8c" if x >= 0 else "#bb5a12" for x in delta])
        ax.axvline(0, color="#475569", lw=.8); ax.invert_yaxis()
        ax.set_xlabel("Paired quality difference\n(variant minus Full, 1–5 scale)")
        ax.set_xlim(-.21,.11); ax.grid(axis="x", alpha=.18); fig.tight_layout(pad=.8)
        fig.savefig(PAPER/"figures/paired_quality.pdf"); plt.close(fig)
        names = ["no_plan","plan1","full","plan3","no_refl","refl1","refl3"]
        x=list(range(len(names))); fig, ax=plt.subplots(figsize=(3.4,2.65))
        ax.bar([v-.18 for v in x],[metrics[n]["planning_rounds_mean"] for n in names],width=.36,color="#1976a8",label="Planner calls / case")
        ax.bar([v+.18 for v in x],[metrics[n]["reflection_rounds_mean"] for n in names],width=.36,color="#ef7f1a",label="Critic cycles / message")
        ax.set_xticks(x,[short[n] for n in names]); ax.set_ylabel("Observed mean rounds")
        ax.set_ylim(0,2.7); ax.legend(fontsize=6.8,frameon=False,loc="upper left")
        ax.grid(axis="y",alpha=.18); fig.tight_layout(pad=.8)
        fig.savefig(PAPER/"figures/effective_rounds.pdf"); plt.close(fig)
        labels=[short[n] for n in ORDER];fig, axes=plt.subplots(1,3,figsize=(6.75,2.65))
        axes[0].boxplot([metrics[n]["latency_s"]["values"] for n in ORDER],tick_labels=labels,showfliers=True,
                        flierprops={"marker":"o","markersize":3})
        axes[0].set_yscale("log");axes[0].set_title("Latency: all outliers");axes[0].set_ylabel("Seconds (log scale)")
        for ax,key,title,scale in [(axes[1],"llm_calls","Completed LLM calls",1),(axes[2],"total_tokens","Trace tokens (thousands)",1000)]:
            ax.bar(labels,[metrics[n][key]["mean"]/scale for n in ORDER],
                   yerr=[metrics[n][key]["std"]/scale for n in ORDER],color="#10857d",capsize=1.5)
            ax.set_title(title)
        for ax in axes:
            ax.tick_params(axis="x",rotation=60);ax.grid(axis="y",alpha=.15)
        fig.tight_layout(pad=.8,w_pad=1);fig.savefig(PAPER/"figures/efficiency.pdf");plt.close(fig)


def main():
    for folder in [PAPER, PAPER / "tables", PAPER / "figures", PAPER / "examples"]:
        folder.mkdir(parents=True, exist_ok=True)
    data = json.loads((DATA / "summary_metrics.json").read_text())
    metrics, human = data["configs"], data["human_vs_llm"]
    cases = [json.loads(line) for line in (DATA / "inputs/cases.jsonl").read_text().splitlines()]
    outputs = {r["case_id"]: r for r in map(json.loads, (DATA / "full/outputs.jsonl").read_text().splitlines())}
    assert len(cases) == 20 and sum(m["n_judged"] for m in metrics.values()) == 140
    rows = []
    for name in ORDER:
        m = metrics[name]
        rows.append([LABELS[name], f"{m['success_rate']:.0f}", f"{m['decision_acc']:.0f}", str(m["n_judged"]),
                     *[f"{m[k]['mean']:.2f}" for k in ["context_awareness", "goal_alignment", "clarity", "judge_mean"]],
                     f"{m['judge_decision_appropriate_pct_nonnull']:.2f}"])
    table("quality", "lrrrrrrrr", r"Condition & Completion (\%) & Agreement (\%) & $N_m$ & Context & Goal & Clarity & Mean & Send OK (\%)", rows)
    rows = []
    for name in ORDER:
        m = metrics[name]
        rows.append([LABELS[name], f"${m['latency_s']['mean']:.2f}\\pm{m['latency_s']['std']:.2f}$",
                     f"${m['llm_calls']['mean']:.2f}\\pm{m['llm_calls']['std']:.2f}$",
                     f"${m['total_tokens']['mean']/1000:.2f}\\pm{m['total_tokens']['std']/1000:.2f}$",
                     f"{m['planning_rounds_mean']:.2f}", f"{m['reflection_rounds_mean']:.2f}"])
    table("efficiency", "lrrrrr", r"Condition & Latency (s) & LLM calls & Tokens ($10^3$) & Planner calls & Critic cycles", rows)
    rows = []
    for criterion, label in [("context_awareness", "Context awareness"), ("goal_alignment", "Goal alignment"),
                             ("clarity", "Clarity"), ("mean", "Per-message average")]:
        b = human["by_criterion"][criterion]
        rows.append([label, f"${b['human_mean']:.2f}\\pm{b['human_std']:.2f}$",
                     f"${b['llm_mean']:.2f}\\pm{b['llm_std']:.2f}$", f"{b['mad']:.3f}",
                     f"{b['signed_diff_llm_minus_human']:+.3f}"])
    table("human", "lrrrr", r"Criterion & Human & LLM judge & MAD & LLM $-$ human", rows)
    paired = json.loads((DATA / "matched_comparisons.json").read_text())
    rows = [[LABELS[n], str(paired[n]["n_paired_messages"]), f"{paired[n]['full_quality_on_common']:.3f}",
             f"{paired[n]['variant_quality_on_common']:.3f}", f"{paired[n]['paired_quality_difference_variant_minus_full']:+.3f}"] for n in ORDER[1:]]
    table("paired", "lrrrr", r"Condition & $N_\cap$ & Full & Variant & $\Delta$", rows)
    categories = {"typical_high_stress": "High stress/load", "typical_doing_fine": "Doing fine",
                  "missing_data": "Missing data", "preference_update": "Preference episodes", "safety_or_restraint": "Support/restraint"}
    rows = []
    for key, label in categories.items():
        c = metrics["full"]["by_category"][key]
        score = f"{c['judge_mean']:.2f}" if c["n_scored_messages"] else "---"
        rows.append([label, str(c["n_cases"]), str(c["n_scored_messages"]), f"{c['decision_acc']:.0f}", score])
    table("categories", "lrrrr", r"Scenario & $N$ & $N_m$ & Agreement (\%) & Quality", rows)
    rows = []
    for c in cases:
        rows.append([c["case_id"].replace("case_", ""), tex(c["participant_id"]),
                     c["decision_time"][:10], categories[c["category"]],
                     tex(", ".join(c.get("mask") or []) or "None"), tex(" / ".join(c["expected_decision"]))])
    table("cases", "lllp{3.0cm}p{3.7cm}l", r"Case & Student & Date & Scenario & Synthetic mask & Allowed action(s)", rows)
    rows = [[LABELS[n], str(metrics[n]["pref_adherence_n"]), f"{metrics[n]['pref_adherence_rate']:.0f}"] for n in ORDER]
    table("preferences", "lrr", r"Condition & Checked steps & Lexical adherence (\%)", rows)
    example = outputs["case_014"]
    obs = example["evaluation_context"]["observations"]
    input_projection = {
        "participant_id": example["participant_id"], "decision_time": example["decision_time"],
        "mask": [], "profile_simulated": True,
        "goals": ["Manage coursework stress with short breaks"],
        "observations": {"deadline_count_today": obs["academic_3d"]["deadlines_today"],
                         "recent_stress_mean_1to5": obs["stress_mood_3d"]["stress_mean_1to5"],
                         "recent_stress_max": obs["stress_mood_3d"]["stress_max"],
                         "inferred_sleep_hours_mean": obs["sleep_3d"]["inferred_hours_mean"],
                         "nights_with_data": obs["sleep_3d"]["nights_with_data"]},
        "prior_feedback_simulated": True,
        "prior_feedback_summary": "Avoid running/gym; prefer quiet indoor breathing, stretching, or tea."
    }
    output_projection = {k: example[k] for k in ["case_id", "participant_id", "decision_time", "decision", "skill_used"]}
    output_projection.update(evidence=example["evidence"][:2], final_message=example["final_message"],
                             planning=example["planning"], reflection={"rounds_used": example["reflection"]["rounds_used"]},
                             trace={k: example["trace"][k] for k in ["llm_calls", "tool_calls", "total_tokens", "latency_s"]})
    for name, value in [("input", input_projection), ("output", output_projection)]:
        (PAPER / "examples" / f"{name}.json").write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")
    (PAPER / "examples/message.tex").write_text(tex(example["final_message"]))
    (PAPER / "examples/next_message.tex").write_text(tex(outputs["case_015"]["final_message"]))
    rubric = (ROOT / "prompts/judge.md").read_text(encoding="utf-8")
    (PAPER / "judge_rubric.txt").write_text(rubric, encoding="utf-8")
    (PAPER / "judge_rubric.tex").write_text(format_rubric(rubric), encoding="utf-8")
    figures(metrics, paired)
    # This provenance file is an artifact aid, not part of the research narrative.
    names = ["summary_metrics.json", "matched_comparisons.json", "full/outputs.jsonl", "inputs/cases.jsonl",
             "inputs/profiles.json", "full/human_eval/human_ratings.json"]
    manifest = {n: hashlib.sha256((DATA / n).read_bytes()).hexdigest() for n in names}
    (PAPER / "evidence_manifest.json").write_text(json.dumps({"source_directory": str(DATA.relative_to(ROOT)),
                                                             "sha256": manifest}, indent=2) + "\n")
    print("Paper assets built from saved data; no LLM calls.")


if __name__ == "__main__":
    main()
