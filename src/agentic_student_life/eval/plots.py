"""Publication-quality matplotlib visualizations for the ICML 2026 report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": 300,
})

CONFIG_LABELS = {
    "full": "Full (P=2, R=2)",
    "single": "Single-Agent",
    "no_plan": "No Planning",
    "plan1": "Plan Depth=1",
    "plan3": "Plan Depth=3",
    "no_refl": "No Reflection",
    "refl1": "Refl Depth=1",
    "refl3": "Refl Depth=3",
    "modelB": "Model B (Alternative)",
}


def generate_depth_plot(
    all_metrics: dict[str, dict[str, Any]],
    output_path: str | Path,
    *,
    include_png: bool = False,
) -> str:
    """Plot judge mean and tokens for planning/reflection budgets from saved metrics."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7))
    sequences = [
        ([("0 (Off)", "no_plan"), ("1", "plan1"), ("2 (Full)", "full"), ("3", "plan3")],
         "Planning Budget (Max Rounds)", "(a) Planning Depth Ablation"),
        ([("0 (Off)", "no_refl"), ("1", "refl1"), ("2 (Full)", "full"), ("3", "refl3")],
         "Reflection Budget (Max Cycles)", "(b) Reflection Depth Ablation"),
    ]
    for ax, (sequence, xlabel, title) in zip(axes, sequences):
        present = [(label, cid) for label, cid in sequence
                   if cid in all_metrics and all_metrics[cid].get("available")]
        if not present:
            continue
        labels = [label for label, _ in present]
        quality = [all_metrics[cid]["judge_mean"]["mean"] for _, cid in present]
        tokens = [all_metrics[cid]["total_tokens"]["mean"] / 1000.0 for _, cid in present]
        token_ax = ax.twinx()
        ax.plot(labels, quality, marker="o", linewidth=2, color="#1d4ed8", label="Judge Mean (1–5)")
        token_ax.plot(labels, tokens, marker="^", linestyle=":", linewidth=1.6,
                      color="#b91c1c", label="Tokens (k)")
        ax.set_ylim(2.5, 5.15)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Quality Score (1–5 scale)")
        token_ax.set_ylabel("Mean Tokens / Case (k)", color="#b91c1c")
        ax.set_title(title)
        ax.grid(True, linestyle="--", alpha=0.4)
        handles, names = ax.get_legend_handles_labels()
        token_handles, token_names = token_ax.get_legend_handles_labels()
        ax.legend(handles + token_handles, names + token_names, loc="lower right", fontsize=7)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    if include_png:
        fig.savefig(output_path.with_suffix(".png"), bbox_inches="tight")
    plt.close(fig)
    return str(output_path)


def generate_all_plots(
    all_metrics: dict[str, dict[str, Any]],
    human_vs_llm: dict[str, Any],
    fig_dir: str | Path = "report/figures",
) -> list[str]:
    """Generate all report figures into `report/figures/`."""
    fdir = Path(fig_dir)
    fdir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    avail_keys = [k for k in CONFIG_LABELS if k in all_metrics and all_metrics[k].get("available")]
    if not avail_keys:
        avail_keys = [k for k, v in all_metrics.items() if v.get("available")]
    if not avail_keys:
        return saved

    # Figure 1: Ablation Overview (Decision Accuracy, Preference Adherence, Judge Score)
    fig, ax1 = plt.subplots(figsize=(7.2, 3.0))
    x = np.arange(len(avail_keys))
    w = 0.27
    labels = [CONFIG_LABELS.get(k, k) for k in avail_keys]
    dec_acc = [all_metrics[k]["decision_acc"] for k in avail_keys]
    pref_adh = [all_metrics[k]["pref_adherence_rate"] if all_metrics[k]["pref_adherence_n"] else np.nan
                for k in avail_keys]
    judge_pct = [all_metrics[k]["judge_mean"]["mean"] * 20.0 for k in avail_keys]

    ax1.bar(x - w, dec_acc, width=w, label="Decision Accuracy (%)", color="#1d4ed8", alpha=0.9)
    ax1.bar(x, pref_adh, width=w, label="Preference Adherence (%)", color="#0f766e", alpha=0.9)
    ax1.bar(x + w, judge_pct, width=w, label="LLM Judge Quality (×20%)", color="#d97706", alpha=0.9)

    ax1.set_ylabel("Score (%)")
    ax1.set_ylim(0, 112)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=22, ha="right")
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.legend(loc="lower right", frameon=True, ncol=3)
    ax1.set_title("Ablation Comparison: Decision Appropriateness, Preference Adherence & Message Quality")
    fig.tight_layout()
    p1 = fdir / "fig1_ablation_overview.pdf"
    fig.savefig(p1, bbox_inches="tight")
    fig.savefig(fdir / "fig1_ablation_overview.png", bbox_inches="tight")
    plt.close(fig)
    saved.append(str(p1))

    # Figure 2: Judge mean and token use under planning/reflection budgets.
    saved.append(generate_depth_plot(all_metrics, fdir / "fig2_depth_curves.pdf", include_png=True))

    # Figure 3: Efficiency (Latency, LLM Calls, Total Tokens across configurations)
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6))
    short_names = {"full": "Full", "single": "Single", "no_plan": "No P", "plan1": "P1",
                   "plan3": "P3", "no_refl": "No R", "refl1": "R1", "refl3": "R3",
                   "modelB": "Model B"}
    short_lbls = [short_names.get(k, k) for k in avail_keys]

    lat_data = [all_metrics[k]["latency_s"]["values"] or [0.0] for k in avail_keys]
    call_means = [all_metrics[k]["llm_calls"]["mean"] for k in avail_keys]
    call_stds = [all_metrics[k]["llm_calls"]["std"] for k in avail_keys]
    tok_means = [all_metrics[k]["total_tokens"]["mean"] / 1000.0 for k in avail_keys]
    tok_stds = [all_metrics[k]["total_tokens"]["std"] / 1000.0 for k in avail_keys]

    bp = axes[0].boxplot(lat_data, tick_labels=short_lbls, patch_artist=True, showfliers=False)
    for patch in bp["boxes"]:
        patch.set_facecolor("#93c5fd")
    axes[0].set_ylabel("End-to-End Latency (s)")
    axes[0].set_title("(a) Per-Case Latency (s)")
    axes[0].tick_params(axis="x", rotation=55, labelsize=7)
    axes[0].grid(axis="y", linestyle="--", alpha=0.4)

    axes[1].bar(np.arange(len(avail_keys)), call_means, yerr=call_stds, capsize=2.5, color="#6ee7b7", edgecolor="#047857")
    axes[1].set_xticks(np.arange(len(avail_keys)))
    axes[1].set_xticklabels(short_lbls, rotation=55, ha="right", fontsize=7)
    axes[1].set_ylabel("LLM Calls / Case")
    axes[1].set_title("(b) Mean LLM Calls")
    axes[1].grid(axis="y", linestyle="--", alpha=0.4)

    axes[2].bar(np.arange(len(avail_keys)), tok_means, yerr=tok_stds, capsize=2.5, color="#fcd34d", edgecolor="#b45309")
    axes[2].set_xticks(np.arange(len(avail_keys)))
    axes[2].set_xticklabels(short_lbls, rotation=55, ha="right", fontsize=7)
    axes[2].set_ylabel("Total Tokens / Case (k)")
    axes[2].set_title("(c) Mean Total Tokens (k)")
    axes[2].grid(axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    p3 = fdir / "fig3_efficiency_boxplots.pdf"
    fig.savefig(p3, bbox_inches="tight")
    fig.savefig(fdir / "fig3_efficiency_boxplots.png", bbox_inches="tight")
    plt.close(fig)
    saved.append(str(p3))

    # Figure 4: Human Judge vs LLM Judge + Confusion Matrix for Full System
    fig, (ax_h, ax_cm) = plt.subplots(1, 2, figsize=(6.8, 2.6))
    if human_vs_llm.get("available"):
        crits = ["context_awareness", "goal_alignment", "clarity", "mean"]
        c_names = ["Context\nAware.", "Goal\nAlign.", "Clarity", "Overall\nMean"]
        h_m = [human_vs_llm["by_criterion"][c]["human_mean"] for c in crits]
        j_m = [human_vs_llm["by_criterion"][c]["llm_mean"] for c in crits]
        mads = [human_vs_llm["by_criterion"][c]["mad"] for c in crits]
        cx = np.arange(len(crits))
        cw = 0.26
        ax_h.bar(cx - cw, h_m, width=cw, label="Human Judge", color="#2563eb")
        ax_h.bar(cx, j_m, width=cw, label="LLM Judge", color="#f59e0b")
        ax_h.bar(cx + cw, mads, width=cw, label="MAD |H - LLM|", color="#ef4444")
        ax_h.set_xticks(cx)
        ax_h.set_xticklabels(c_names)
        ax_h.set_ylim(0, 5.4)
        ax_h.set_ylabel("Score (1–5) / MAD")
        ax_h.set_title(f"(a) Human vs. LLM Judge (n={human_vs_llm['n_paired']})")
        ax_h.grid(axis="y", linestyle="--", alpha=0.4)
        ax_h.legend(loc="upper right", fontsize=7)

    ref_key = "full" if "full" in all_metrics else avail_keys[0]
    conf = all_metrics[ref_key].get("confusion", {})
    acts = ["suggest", "ask", "none"]
    mat = np.array([[conf.get(r_act, {}).get(c_act, 0) for c_act in acts] for r_act in acts], dtype=int)
    im = ax_cm.imshow(mat, cmap="Blues")
    ax_cm.set_xticks(range(3))
    ax_cm.set_yticks(range(3))
    ax_cm.set_xticklabels(acts)
    ax_cm.set_yticklabels(acts)
    ax_cm.set_xlabel("Predicted Decision")
    ax_cm.set_ylabel("Expected Decision")
    ax_cm.set_title(f"(b) Decision Confusion ({CONFIG_LABELS.get(ref_key, ref_key)})")
    for i in range(3):
        for j in range(3):
            ax_cm.text(
                j, i, str(mat[i, j]),
                ha="center", va="center",
                color="white" if mat[i, j] > mat.max() / 2 else "#0f172a",
                fontweight="bold",
            )
    plt.colorbar(im, ax=ax_cm, fraction=0.046, pad=0.04)

    fig.tight_layout()
    p4 = fdir / "fig4_human_vs_judge.pdf"
    fig.savefig(p4, bbox_inches="tight")
    fig.savefig(fdir / "fig4_human_vs_judge.png", bbox_inches="tight")
    plt.close(fig)
    saved.append(str(p4))

    return saved

