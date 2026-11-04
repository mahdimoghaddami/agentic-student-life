"""Blind human rating sheet exporter and Human vs. LLM Judge comparison analyzer."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any

import numpy as np


def export_human_sheet(
    *,
    run_dir: str | Path = "runs/full",
    cases_by_id: dict[str, dict[str, Any]],
    profiles: dict[str, Any],
    out_dir: str | Path = "runs/full/human_eval",
    max_items: int = 15,
) -> dict[str, str]:
    """Export a blind rating sheet (CSV + HTML + JSON template) with >=10 non-null messages
    and NO LLM judge scores visible."""
    rdir = Path(run_dir)
    outputs_path = rdir / "outputs.jsonl"
    if not outputs_path.exists():
        raise FileNotFoundError(f"Missing outputs.jsonl in {rdir}")

    records = [
        json.loads(line)
        for line in outputs_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    non_null = [
        r for r in records
        if r.get("status") == "ok" and r.get("final_message") and str(r.get("final_message")).strip()
    ]
    selected = non_null[:max_items]

    odir = Path(out_dir)
    odir.mkdir(parents=True, exist_ok=True)
    csv_path = odir / "blind_rating_sheet.csv"
    html_path = odir / "blind_rating_sheet.html"
    json_path = odir / "human_ratings.json"

    rows = []
    for idx, r in enumerate(selected, 1):
        cid = r["case_id"]
        uid = r["participant_id"]
        case = cases_by_id.get(cid, {})
        prof = profiles.get(uid, {})
        ev_summaries = [
            f"[{e.get('source')}] {e.get('detail')}"
            for e in r.get("evidence", [])
        ]
        rows.append(
            {
                "item_num": idx,
                "case_id": cid,
                "participant_id": uid,
                "decision_time": r["decision_time"],
                "category": r.get("category", ""),
                "decision": r["decision"],
                "skill_used": r.get("skill_used") or "",
                "student_goals": "; ".join(prof.get("goals", [])),
                "student_preferences": json.dumps(prof.get("preferences", {})),
                "case_context_rationale": case.get("rationale", ""),
                "evidence_summary": " | ".join(ev_summaries),
                "final_message": r["final_message"],
                "human_context_awareness_1_to_5": "",
                "human_goal_alignment_1_to_5": "",
                "human_clarity_1_to_5": "",
                "human_notes": "",
            }
        )

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    # Build clean standalone HTML sheet for easy blind rating
    cards_html = []
    for row in rows:
        cards_html.append(
            f"""
            <div class="card">
              <h3>Item #{row['item_num']} — <code>{html.escape(row['case_id'])}</code> ({html.escape(row['category'])})</h3>
              <p><strong>Participant:</strong> {html.escape(row['participant_id'])} | <strong>Time:</strong> {html.escape(row['decision_time'])} | <strong>Decision:</strong> <code>{html.escape(row['decision'])}</code> ({html.escape(row['skill_used'])})</p>
              <p><strong>Simulated Goals:</strong> {html.escape(row['student_goals'])}</p>
              <p><strong>Simulated Preferences:</strong> <code>{html.escape(row['student_preferences'])}</code></p>
              <p><strong>Available Context / Evidence:</strong> {html.escape(row['evidence_summary'])}</p>
              <div class="msg"><strong>Coach Final Message:</strong><br>{html.escape(row['final_message'])}</div>
              <p class="rubric">Rate 1–5 (1=Poor, 3=Adequate, 5=Excellent): Context Awareness: [ ___ ] &nbsp;|&nbsp; Goal Alignment: [ ___ ] &nbsp;|&nbsp; Clarity: [ ___ ]</p>
            </div>
            """
        )
    html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Blind Human Evaluation Sheet</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 920px; margin: 24px auto; padding: 0 16px; color: #1e293b; }}
.card {{ border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; margin-bottom: 16px; background: #f8fafc; }}
.msg {{ background: #ffffff; border-left: 4px solid #2563eb; padding: 12px; margin: 10px 0; font-size: 1.05em; }}
.rubric {{ font-weight: 600; color: #0f172a; }}
</style></head><body>
<h1>Blind Human Judge Evaluation Sheet ({len(rows)} Messages)</h1>
<p>Rate each message independently from <strong>1 to 5</strong> on <em>Context Awareness</em>, <em>Goal Alignment</em>, and <em>Clarity</em> using the same rubric as the LLM Judge, <strong>before</strong> viewing LLM Judge scores.</p>
{''.join(cards_html)}
</body></html>"""
    html_path.write_text(html_doc, encoding="utf-8")

    if not json_path.exists():
        template = [
            {
                "case_id": row["case_id"],
                "category": row["category"],
                "decision": row["decision"],
                "final_message": row["final_message"],
                "context_awareness": None,
                "goal_alignment": None,
                "clarity": None,
                "notes": "",
            }
            for row in rows
        ]
        json_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

    return {
        "csv_path": str(csv_path),
        "html_path": str(html_path),
        "json_path": str(json_path),
        "num_items": str(len(rows)),
    }


def compute_human_vs_llm(
    *,
    judge_scores_path: str | Path = "runs/full/judge_scores.jsonl",
    human_ratings_path: str | Path = "runs/full/human_eval/human_ratings.json",
) -> dict[str, Any]:
    """Compare human ratings against LLM judge scores and compute Mean Absolute Difference (MAD)
    and notable disagreements."""
    jpath = Path(judge_scores_path)
    hpath = Path(human_ratings_path)
    if not jpath.exists() or not hpath.exists():
        return {"available": False}

    j_map: dict[str, dict[str, Any]] = {}
    for line in jpath.read_text(encoding="utf-8").splitlines():
        if line.strip():
            obj = json.loads(line)
            j_map[obj["case_id"]] = obj

    h_list = json.loads(hpath.read_text(encoding="utf-8"))
    paired = []
    for h in h_list:
        cid = h.get("case_id")
        if (
            cid in j_map
            and h.get("context_awareness") is not None
            and h.get("goal_alignment") is not None
            and h.get("clarity") is not None
        ):
            j = j_map[cid]
            h_ca = float(h["context_awareness"])
            h_ga = float(h["goal_alignment"])
            h_cl = float(h["clarity"])
            h_mean = (h_ca + h_ga + h_cl) / 3.0

            j_ca = float(j["context_awareness"])
            j_ga = float(j["goal_alignment"])
            j_cl = float(j["clarity"])
            j_mean = (j_ca + j_ga + j_cl) / 3.0

            paired.append(
                {
                    "case_id": cid,
                    "category": j.get("category", h.get("category", "")),
                    "final_message": j.get("final_message", h.get("final_message", "")),
                    "human": {
                        "context_awareness": h_ca,
                        "goal_alignment": h_ga,
                        "clarity": h_cl,
                        "mean": round(h_mean, 3),
                        "notes": h.get("notes", ""),
                    },
                    "llm": {
                        "context_awareness": j_ca,
                        "goal_alignment": j_ga,
                        "clarity": j_cl,
                        "mean": round(j_mean, 3),
                        "justification": j.get("justification", ""),
                    },
                    "abs_diff": {
                        "context_awareness": abs(h_ca - j_ca),
                        "goal_alignment": abs(h_ga - j_ga),
                        "clarity": abs(h_cl - j_cl),
                        "mean": round(abs(h_mean - j_mean), 3),
                        "max_criterion_diff": max(abs(h_ca - j_ca), abs(h_ga - j_ga), abs(h_cl - j_cl)),
                    },
                }
            )

    if not paired:
        return {"available": False, "n_paired": 0}

    criteria = ("context_awareness", "goal_alignment", "clarity", "mean")
    summary_by_criterion: dict[str, Any] = {}
    for crit in criteria:
        h_vals = np.array([p["human"][crit] for p in paired], dtype=float)
        j_vals = np.array([p["llm"][crit] for p in paired], dtype=float)
        diffs = np.abs(h_vals - j_vals)
        exact_agree = float(np.mean(diffs == 0)) if crit != "mean" else float(np.mean(diffs <= 0.34))
        within_one = float(np.mean(diffs <= 1.0))
        summary_by_criterion[crit] = {
            "human_mean": round(float(np.mean(h_vals)), 2),
            "human_std": round(float(np.std(h_vals, ddof=1 if len(h_vals) > 1 else 0)), 2),
            "llm_mean": round(float(np.mean(j_vals)), 2),
            "llm_std": round(float(np.std(j_vals, ddof=1 if len(j_vals) > 1 else 0)), 2),
            "mad": round(float(np.mean(diffs)), 3),
            "signed_diff_llm_minus_human": round(float(np.mean(j_vals - h_vals)), 3),
            "exact_agreement_rate": round(exact_agree, 3),
            "within_1pt_rate": round(within_one, 3),
        }

    disagreements = sorted(
        paired,
        key=lambda x: (x["abs_diff"]["max_criterion_diff"], x["abs_diff"]["mean"]),
        reverse=True,
    )

    return {
        "available": True,
        "n_paired": len(paired),
        "by_criterion": summary_by_criterion,
        "paired_items": paired,
        "notable_disagreements": disagreements[:4],
    }

