"""Build the corrected ICML report from saved metrics; makes no API calls."""
import json
from pathlib import Path
import shutil

ROOT = Path("runs_corrected/2026-11-04_v3")


def escape(value):
    result = str(value)
    for old, new in [("\\", r"\textbackslash{}"), ("_", r"\_"), ("%", r"\%"),
                     ("&", r"\&"), ("#", r"\#")]:
        result = result.replace(old, new)
    return result


def main():
    data = json.loads((ROOT / "summary_metrics.json").read_text())
    metrics = data["configs"]
    human = data["human_vs_llm"]
    comparisons = json.loads((ROOT / "matched_comparisons.json").read_text())
    report = ROOT / "report"
    report.mkdir(exist_ok=True)
    for name in ["icml2026.sty", "icml2026.bst", "algorithm.sty", "algorithmic.sty", "fancyhdr.sty", "example_paper.bib"]:
        shutil.copy2(Path("report") / name, report / name)
    (report / "rubric.txt").write_text(Path("prompts/judge.md").read_text(encoding="utf-8").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"'), encoding="utf-8")
    full = metrics["full"]
    names = ["full", "single", "no_refl", "no_plan", "refl1", "refl3", "plan1", "plan3", "modelB"]
    efficiency = []
    paired = []
    preference_notes = []
    for name in names:
        m = metrics[name]
        efficiency.append(f"{escape(name)} & {m['latency_s']['mean']:.2f} $\\pm$ {m['latency_s']['std']:.2f} & {m['llm_calls']['mean']:.2f} & {m['total_tokens']['mean']:,.0f} & {m['planning_rounds_mean']:.2f} & {m['reflection_rounds_mean']:.2f} \\\\")
        if name != "full":
            c = comparisons[name]
            paired.append(f"{escape(name)} & {c['n_paired_messages']} & {c['full_quality_on_common']:.3f} & {c['variant_quality_on_common']:.3f} & {c['paired_quality_difference_variant_minus_full']:+.3f} \\\\")
        for cid, violations in m["pref_adherence_violations"].items():
            if violations:
                preference_notes.append(f"\\item \\texttt{{{escape(name)}/{escape(cid)}}}: {escape('; '.join(violations))}.")
    cost = data["costs"]
    generation_cost = sum(cost[n]["successful_response_estimate_usd"] for n in names)
    uncertain = sum(cost[n]["uncertain_failure_upper_bound_usd"] for n in names)
    attempts = sum(cost[n]["failed_provider_attempts"] for n in names)
    successful_requests = sum(cost[n]["successful_provider_requests"] for n in names)
    rows = "\n".join(efficiency)
    paired_rows = "\n".join(paired)
    pref_notes = "\n".join(preference_notes) or r"\item No proxy violations were recorded."
    text = r"""\documentclass{article}
\usepackage{microtype,graphicx,booktabs,hyperref,listings}
\newcommand{\theHalgorithm}{\arabic{algorithm}}
\usepackage[preprint]{icml2026}
\usepackage{amsmath}
\icmltitlerunning{Corrected StudentLife Stress-Coach Evaluation}
\lstset{basicstyle=\ttfamily\scriptsize,breaklines=true,columns=fullflexible}
\begin{document}
\twocolumn[
\icmltitle{A Multi-Agent Student Stress Coach:\\Corrected Evaluation on Longitudinal StudentLife Cases}
\icmlsetsymbol{equal}{*}
\begin{icmlauthorlist}
\icmlauthor{Mahdi Moghaddami}{equal,ou}
\icmlauthor{Brett Piggott}{equal,ou}
\end{icmlauthorlist}
\icmlaffiliation{ou}{Department of Computer Science and Engineering, Oakland University}
\icmlcorrespondingauthor{Mahdi Moghaddami}{moghaddami@oakland.edu}
\vskip 0.3in]
\printAffiliationsAndNotice{\icmlEqualContribution}
\begin{abstract}
We evaluate a training-free student stress coach that combines planning, tool use, multi-agent interaction, reflection, and persistent memory with modular coaching skills. A corrected experiment uses the same 20 historical decision cases across nine configurations, with one fixed model per condition and a separate OpenAI judge. The full system completes all cases and matches all hand-authored allowed decisions. Its @JUDGED@ non-null messages receive a mean quality score of @QUALITY@/5. One human independently rates 10 messages before automated judging; the mean absolute difference across 30 criterion ratings is @MAD@ points. We report the required structural, depth, and model comparisons, including matched-message quality, efficiency, and measurement limitations. These small, selected-case results measure software behavior; they do not establish student well-being benefits or population-level superiority.
\end{abstract}

\section{Task, Data, and Evaluation Cases}
The coach chooses \texttt{suggest}, \texttt{ask}, or \texttt{none} at a historical participant-specific decision time. StudentLife supplies passive sensing and self-reported well-being information over a Dartmouth term \cite{wang2014studentlife}. The local archive has 49 participant identifiers; preprocessing covers all 49. Evaluation uses 20 manually selected cases from eight participants, rather than 20 independent students.

The features used are inferred sleep, physical activity, conversation, phone-use indicators, EMA stress/mood/sleepiness, and academic schedule or deadline context. Tools summarize recent windows and compare behavior with a personal baseline. Daily sensing aggregates use completed days before the decision; EMA records are restricted to their exact timestamps. Missing course periods are handled explicitly as partial schedules. Grades, final GPA, post-term surveys, and Piazza activity are not used as historical coaching inputs. Pre-term psychological surveys supply background, rather than future outcome labels.

StudentLife does not provide coaching goals, preferences, or replies to suggestions. Deterministic profiles and scripted feedback are explicitly labeled simulated. Two three-step preference episodes test whether later messages use earlier feedback. The cohort includes five high-stress/load cases, three doing-fine cases, four natural or masked missing-data cases, six preference-episode cases, and two safety/restraint cases. Case definitions, timestamps, masks, and feedback are frozen under \texttt{inputs/}. Allowed decisions are hand-authored benchmark expectations, not observed student outcomes.

\section{Architecture and Agentic Patterns}
The full system has five role-prompted agents, all using Model A. The \emph{Planner} proposes checks and chooses a response policy. The \emph{Context Analyst} invokes read-only Python tools for evidence. The \emph{Message Writer} drafts using a selected coaching skill. The \emph{Critic} reviews grounding, preferences, safety, and clarity and can request revision. The \emph{Memory Manager} extracts durable preferences after simulated feedback. Role separation is implemented in code, rather than inferred from model prose.

\paragraph{Planning.} A round is one Planner invocation. The full budget is two rounds; the depth-one variant gathers evidence before its single Planner call. Larger budgets add bounded reassessment, with no finalization call outside the limit.
\paragraph{Tool use.} Callable tools expose sensing, EMA, academic, time, baseline, and curated resource summaries. Tool queries are bounded by the decision timestamp and simulated masks; no tool exposes expected decisions or future feedback.
\paragraph{Skills.} Eight Markdown coaching modules guide concrete message styles, such as a manageable break, sleep support, clarification, or resource awareness. These are local instructions, not model training. Campus resources are curated project content rather than a StudentLife data stream.
\paragraph{Reflection.} The Critic can approve or request revision. Budgets specify maxima, so an approved message may use only one cycle even when two or three are allowed. Final decision, skill, and message are synchronized after reflection.
\paragraph{Memory and interaction.} Per-student JSON files store episodic history and learned preferences. Reads include only interactions strictly earlier than the decision. Each participant executes chronologically across episode IDs; different participants can run concurrently. Resume reconstructs a compatible completed prefix. Atomic memory updates prevent competing writes. The single-agent baseline receives the same input definitions, profiles/history machinery, tools, and skills, combining the main reasoning roles; its memory extraction still follows the shared persistence pipeline.

\paragraph{Worked example.} For \texttt{case\_009}, the available history contains natural sensing gaps. The tools expose missing recent sleep/activity evidence rather than filling it with invented values. The coach selects \texttt{ask} and acknowledges that the data have not come through before asking about current energy and stress. The writer uses the clarification skill, the critic reviews the draft, and the output preserves the evidence and execution trace. A missing observation therefore changes the response policy as well as the wording.

\section{Corrected Experimental Protocol}
Model A is \texttt{gemini-3.6-flash}; Model B is \texttt{gemini-3.5-flash-lite}. Generation uses temperature 0.3 (0.1 for Critic and Memory Manager), low thinking, and an 8,192-token output cap. Four worker threads process independent participant histories, with shared one-second request spacing per credential. Retries retain the configured model. Two Gemini credentials are supported, but only the primary key was needed for the completed full run.

The full condition enables planning (maximum two rounds), reflection (maximum two cycles), tools, skills, and history of up to five interactions. Eight additional conditions implement exactly the required comparisons: single-agent; no reflection; no planning; reflection maxima one and three; planning maxima one and three; and Model B with the full architecture. All use the same 20 case definitions and regenerated profiles. Histories can diverge across conditions because earlier messages and extracted preferences are part of the treatment.

Source/data/configuration manifests prevent incompatible resume. The completed full baseline and its human ratings are reused unchanged; it is not regenerated for each comparison. Earlier attempts \texttt{v1} and \texttt{v2} are retained but excluded from results: the first was interrupted for code fixes and the second for free-tier quota exhaustion. The valid suite is \texttt{2026-11-04\_v3}.

\subsection{Independent Automated and Human Evaluation}
The judge is the pinned \texttt{gpt-5.4-mini-2026-03-17} snapshot at temperature zero, reasoning disabled, and a 2,048-token completion cap. It scores every successful non-null message on context awareness, goal alignment, and clarity (integer 1--5), plus whether sending that message was appropriate. Silence is evaluated by the allowed-decision check; it receives no invented message score.

Human and automated evaluation receive the same frozen evidence summary, simulated profile, learned preferences, prior interactions, decision, and message. Expected labels, case-selection rationale, and current-case feedback are excluded. Cached judge results are reused only when the message, context, rubric, model, and temperature fingerprint match. The complete anchored rubric is reproduced in Appendix~\ref{app:rubric}.

Mahdi independently rated 10 messages on the same three criteria and committed those ratings before the first automated call. Items followed a scenario-based priority declared before generation, skipping null messages; this was not a random or representative sample. There is one human rater. We report criterion-level mean absolute difference (MAD), separately from MAD after averaging each message's three scores, since averaging can hide opposing disagreements.

\section{Results}
\begin{table*}[t]
\caption{Full-system results by case category. Decisions are compared with manually specified allowed labels. Quality uses only non-null messages.}
\centering\resizebox{\textwidth}{!}{\input{tables/table1_main_results.tex}}
\end{table*}
\begin{table*}[t]
\caption{Required controlled comparisons. Each row has 20 cases. Preference adherence is a four-case lexical/theme/length proxy, not a semantic or clinical outcome. Quality means may have different non-null cohorts; paired comparisons appear below.}
\centering\resizebox{\textwidth}{!}{\input{tables/table2_ablations.tex}}
\end{table*}
\begin{table*}[t]
\caption{Human versus automated ratings on the same 10 messages. The mean-score row averages criteria within each message; its MAD can be smaller than criterion-level MAD.}
\centering\resizebox{\textwidth}{!}{\input{tables/table3_human_vs_llm.tex}}
\end{table*}

The full configuration completes 20/20 cases, matches an allowed decision in 20/20, and satisfies the four applicable preference proxy checks. Its @JUDGED@ messages score @QUALITY@/5 on average. This is a selected software benchmark with expected labels authored by the project, not independently measured decision correctness in a deployed setting.

Across the 30 human--judge criterion pairs, MAD is @MAD@ points. Per-criterion MADs are 0.10 for context awareness, 0.30 for goal alignment, and 0.40 for clarity. The largest difference is \texttt{case\_002}: human clarity 5 versus judge clarity 3. The judge describes the bedtime suggestion as wordy and overly certain; the human recorded no explanatory note, so we cannot infer their reasoning. Other one-point disagreements show that high average agreement can coexist with different views of concision and preference alignment.

\subsection{Ablation Interpretation}
The comparisons vary architecture, planning, reflection, and model while preserving input definitions and fixed-model retry policy. The table below restricts quality to identical case IDs where both conditions sent a message. It avoids interpreting a change in the number of messages as an automatic change in writing quality.
\begin{table}[t]
\caption{Paired message quality on common non-null cases. Positive $\Delta$ favors the variant. Single-run descriptive differences are not significance tests.}
\centering\small
\begin{tabular}{lrrrr}\toprule
Variant & $N$ & Full & Variant & $\Delta$\\\midrule
@PAIRED_ROWS@
\bottomrule\end{tabular}
\end{table}
\begin{figure*}[t]\centering
\includegraphics[width=.95\textwidth]{figures/fig2_depth_curves.pdf}
\caption{Planning and reflection \emph{maximum} budgets, with quality and token use. Decision accuracy is divided by 20 for plotting on the quality axis; it remains a percentage-based benchmark proxy.}
\end{figure*}
\begin{figure}[t]\centering
\includegraphics[width=\columnwidth]{figures/fig7_effective_rounds.pdf}
\caption{Observed rounds distinguish a maximum budget from work actually performed. Reflection can stop early after approval.}
\end{figure}

The prespecified full condition remains the final configuration and retains five interacting roles and all five requested patterns. These runs expose tradeoffs; a small, unrepeated benchmark with ceiling effects is insufficient to select a globally best design or claim that extra agents or cycles reliably improve outcomes. Model B is evaluated under the same architecture; its results should be read alongside efficiency and any behavioral differences, not latency alone.

\subsection{Preference Proxy Review}
Preference adherence checks prior feedback for forbidden words, required themes, and the latest length limit. It is measured on four later preference steps. The single-agent \texttt{case\_014} contains ``stress running elevated,'' which the lexical check flags as forbidden ``running'' despite offering indoor tea, stretching, or breathing. We retain the proxy result and identify this false positive rather than rerun the model or silently change the benchmark. All recorded proxy flags follow; their meaning requires reading the message and prior feedback.
\begin{itemize}
@PREF_NOTES@
\end{itemize}

\subsection{Efficiency and Cost}
\begin{table*}[t]
\caption{Per-case efficiency from execution traces. Latency includes tools, memory, request pacing and retries, excludes judging. Calls/tokens count completed model steps; provider-ledger totals additionally capture successful responses inside attempts that later failed. Actual planning and reflection rounds show early stopping.}
\centering\small
\begin{tabular}{lrrrrr}\toprule
Configuration & Latency $\mu\pm\sigma$ (s) & Calls & Tokens & Plan rounds & Critic cycles/msg\\\midrule
@EFFICIENCY_ROWS@
\bottomrule\end{tabular}
\end{table*}
Full-system latency averages @LATENCY@ seconds per case, with @CALLS@ completed model calls and @TOKENS@ trace tokens on average. The provider logs separately record @SUCCESS_REQUESTS@ successful generation requests and @FAILED_ATTEMPTS@ failed attempts across the nine conditions. Transient server errors affect wall-clock comparisons; this is not an isolated hardware benchmark. No additional samples were generated to improve the reported scores.

Successful-response generation charges are estimated at \$@GEN_COST@ across the nine conditions, excluding preflight and interrupted attempts. The ledger assigns a further \$@UNCERTAIN@ conservative upper bound to uncertain failures; this is not confirmed billed spend. Automated judging costs an estimated \$@JUDGE_COST@. Estimates use token prices without cached-input discounts and do not verify account credit balances. Preflight and earlier-attempt ledgers remain separate.

\section{Limitations and Responsible Interpretation}
Cases were selected for scenario coverage and include repeated participants. Simulated goals and scripted feedback are not evidence of real student preferences or acceptance. Sleep/activity inferences and sparse EMA observations can be noisy. The deterministic preference proxy has lexical false positives; the allowed-decision test and LLM judge have their own author and model biases. One rater and one generation per condition do not support reliable population-level or causal superiority claims. Scores near the top of the rubric can mask meaningful message differences.

Curated campus-resource entries are demonstration content and are not continuously verified institutional service data. The historical timeline also differs from the present-day language-model environment. This is an offline educational coach simulation, not a deployed clinical service or evidence of improved mental health. A deployment would require consent, institutional resource validation, privacy controls, and prospective evaluation.

\section{Reproducibility and Conclusion}
The valid outputs, call traces, memory snapshots, generation configuration snapshots, manifests, per-request usage ledgers, human ratings, and judge scores are under \texttt{runs\_corrected/2026-11-04\_v3/}. The repository includes resume-safe scripts for only the eight missing ablations, judging saved messages, offline analysis, and report generation. Thirty offline regression tests and five leakage checks pass. Hash checks preserve all 127 original run files plus the full corrected baseline and human ratings.

The corrected experiment demonstrates all required patterns and comparisons without reusing incompatible historical scores. It supports descriptive analysis of execution, quality, preference handling, and efficiency on the chosen cases. Further claims need broader cases, repeated seeds, stronger semantic checks, and independent raters.

\bibliography{example_paper}
\bibliographystyle{icml2026}
\clearpage\appendix\onecolumn
\section{Complete Judge Prompt and Anchored Rubric}\label{app:rubric}
This is the rubric shown to the human rater and used unchanged for automated evaluation. The transport constrains automated output to three integer scores, decision appropriateness, and a short justification. Scores and context are fingerprinted against the saved message.
\lstinputlisting{rubric.txt}
\section{Commands and Evidence Locations}
Commands run from the repository root. The generation command resumes matching outputs; do not use reset or no-resume flags merely to reproduce analysis.
\begin{lstlisting}
uv run python -B scripts/run_corrected_ablations.py
uv run python -B scripts/judge_corrected.py --runs full single no_refl no_plan refl1 refl3 plan1 plan3 modelB
uv run python -B scripts/analyze_corrected.py
uv run python -B scripts/build_corrected_report.py
latexmk -pdf -interaction=nonstopmode -halt-on-error -cd runs_corrected/2026-11-04_v3/report/corrected_report.tex
\end{lstlisting}
Each configuration's \texttt{outputs.jsonl} has one final object per case; \texttt{failed\_cases.json} lists execution failures, and \texttt{api\_usage.jsonl} records observed provider usage without credentials or prompt bodies. \texttt{summary\_metrics.json}, \texttt{matched\_comparisons.json}, and \texttt{comparison.csv} provide machine-readable metrics. Human ratings remain associated with their message/context fingerprints. The original \texttt{runs/} and earlier report remain historical evidence and are excluded from corrected comparisons.
\end{document}
"""
    values = {
        "JUDGED": full["n_judged"], "QUALITY": f"{full['judge_mean']['mean']:.2f}",
        "MAD": f"{human['all_criterion_ratings_mad']:.3f}", "PAIRED_ROWS": paired_rows,
        "EFFICIENCY_ROWS": rows, "PREF_NOTES": pref_notes,
        "LATENCY": f"{full['latency_s']['mean']:.2f}", "CALLS": f"{full['llm_calls']['mean']:.2f}",
        "TOKENS": f"{full['total_tokens']['mean']:,.0f}", "GEN_COST": f"{generation_cost:.3f}",
        "UNCERTAIN": f"{uncertain:.3f}", "JUDGE_COST": f"{cost['judge']['estimated_usd']:.3f}",
        "SUCCESS_REQUESTS": successful_requests, "FAILED_ATTEMPTS": attempts,
    }
    for key, value in values.items():
        text = text.replace(f"@{key}@", str(value))
    assert "@PAIRED" not in text
    (report / "corrected_report.tex").write_text(text, encoding="utf-8")
    print(report / "corrected_report.tex")


if __name__ == "__main__":
    main()
