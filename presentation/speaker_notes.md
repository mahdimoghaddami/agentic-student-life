# StudentLife Stress Coach: speaker notes

Slides 1-8 form the five-minute talk. Slides 9-11 are backup material for questions.

| Slide | Time | Elapsed |
|---|---:|---:|
| 1. Title | 15 s | 0:15 |
| 2. The coaching task | 40 s | 0:55 |
| 3. Five interacting roles | 55 s | 1:50 |
| 4. Five required design patterns | 25 s | 2:15 |
| 5. Memory across interactions | 45 s | 3:00 |
| 6. Full-system results | 50 s | 3:50 |
| 7. Ablation tradeoffs | 45 s | 4:35 |
| 8. Conclusions | 25 s | 5:00 |

## 1. Title

We built a language-agent coach that uses a student's changing circumstances and earlier feedback to decide when support is appropriate. The project focuses on personalized suggestions and questions, including the choice to remain silent.

## 2. The coaching task

StudentLife supplies historical sensing, self-reports and academic context. The local activity archive contains 49 identifiers, while the published study describes 48 students. We evaluate 20 selected cases from eight participants. Goals and coaching preferences are absent from StudentLife, so we label those profiles and scripted replies as simulated. The cases include high stress, doing well, missing observations and preference updates. We expose only observations available at each decision time, plus earlier interactions. Upcoming syllabus deadlines are assumed known.

## 3. Five interacting roles

A deterministic orchestrator coordinates five prompted roles. The Planner asks for checks. The Analyst queries bounded tools and returns findings. The Planner then selects an action and skill. The Writer drafts a message, and the Critic either approves it or requests revision within the budget. A silent decision can skip writing and review. After the action, the Memory Manager extracts rules from any available simulated feedback. JSON files retain episodes and rules for later decisions. The final JSONL record includes evidence, context, memory updates and execution traces. This diagram simplifies conditional branches and serialization.

## 4. Five required design patterns

All five required patterns are enabled in the full configuration. Planning and reflection each have a maximum budget of two. Tools expose data and campus-resource search, while eight Markdown skills guide the Writer. Memory keeps five recent episodes and earlier learned rules. TOML controls let us disable or vary components. The coaching model is Gemini 3.6 Flash; a separate OpenAI model judges messages. No training or fine-tuning is involved.

## 5. Memory across interactions

This is an actual saved example for participant u16. The simulated April 15 reply prefers quiet breaks. Feedback after the April 18 message adds a library setting and a length limit below 35 words. The April 22 output is 28 words and proposes quiet breathing and tea at the student's desk. The new feedback becomes available only after its own interaction. This example demonstrates access to prior preferences, but the initial profile already favors quiet breaks, so it does not isolate a causal improvement from memory.

## 6. Full-system results

The full system completes all 20 cases and matches every manually allowed action. It sends 13 suggestions and three questions and stays silent four times. The independent judge gives the 16 messages an average quality of 4.81 out of five. A human independently scores 10 messages before seeing the judge scores. The table compares those same 10 messages. The mean absolute difference across 30 individual criterion ratings is 0.267; clarity has the largest mean gap. Mean latency is 35.59 seconds, with 6.20 model calls and 17,529 tokens per case. Judging is excluded from that latency.

## 7. Ablation tradeoffs

Nine conditions produce 180 valid final outputs. The single coach matches the full system's rounded quality and allowed-action agreement with fewer model calls. It uses more tokens, however: about 18.68 thousand versus 17.53 thousand. Model B obtains the highest mean quality, 4.89, but matches 19 of 20 allowed decisions. Increasing maximum planning or reflection budgets does not consistently improve results. These are descriptive comparisons from one generation per condition. Message cohorts, earlier generated histories and remote-service latency can differ. The consolidated coach also retains auxiliary feedback extraction.

## 8. Conclusions

The architecture makes the system's evidence, plans, critiques and remembered preferences inspectable. Our experiments show tradeoffs rather than a consistent advantage for more roles or larger budgets. The benchmark is small, preferences and replies are simulated, and one person supplies human ratings. We measure offline coaching behavior, not reductions in real student stress. Both authors contributed approximately equally through the responsibilities shown.

## Backup notes

- **Slide 9:** Final completion is 100% for all conditions. Planning maximum three initially had one timeout; reported latency/calls/tokens include the preserved recovery accounting. Actual reflection depth averages one review per sent message at all three maxima. Different maximum settings therefore did not create deeper executed reviews here.
- **Slide 10:** The Analyst has eight data/resource functions. Writer tool use consists of skill loading. The single coach also has memory recall. Campus resources are a static curated catalogue. Skill applicability rules guide generation; they are not deterministic output guarantees.
- **Slide 11:** Model A and B share the full architecture and role temperatures. The judge uses a fixed OpenAI snapshot, temperature zero, reasoning disabled and a 2,048-token completion cap. The JSON projection is from case_015 and omits fields for readability. A complete record includes evidence, frozen context, plans, critiques and memory updates.
- Daily features precede the decision date. A same-day last-night estimate becomes available after noon; EMA timestamps cannot exceed the decision time. Memory must be strictly earlier.
- Two unmasked absence cases occur after passive recording ended; they are not demonstrated in-term sensor malfunctions. Two other cases use explicitly synthetic masks.
- Expected actions are authored evaluation references. Agents and evaluators do not receive them. The shared evaluator packet may omit dynamically retrieved context seen by the coach.

## Sources

- [Project requirements](../project_doc.pdf), especially the five-minute presentation guidance.
- [Comparison CSV](../runs_corrected/2026-11-04_v3/comparison.csv) and [detailed metrics](../runs_corrected/2026-11-04_v3/summary_metrics.json): slides 6, 7 and 9.
- [Full outputs](../runs_corrected/2026-11-04_v3/full/outputs.jsonl), case_015: slides 5 and 11.
- [Cases](../cases/cases.jsonl), [profiles](../cases/profiles.json) and [feedback scripts](../cases/feedback_scripts.json): slides 2 and 5.
- [Orchestrator](../src/agentic_student_life/orchestrator.py), [tools](../src/agentic_student_life/tools/__init__.py), [skill library](../src/agentic_student_life/skills/library.py) and [configuration](../configs/2026-11-04/full-paid.toml): slides 3, 4 and 10.
- [Judge configuration](../configs/2026-11-04/judge.toml), [judge transport](../scripts/judge_corrected.py) and [rubric](../prompts/judge.md): slides 6 and 11.
