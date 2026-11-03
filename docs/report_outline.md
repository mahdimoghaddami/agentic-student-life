# Report scaffold — fill with actual results

## Problem and research question
When do planning and reflection improve a personalized student coach sufficiently
to justify extra calls, tokens, and latency? Define everyday support and its limits.

## Data and simulation
Describe StudentLife streams, verified code mappings, timestamps, availability,
window lengths, missingness, observation counts, selected participants/cases, and
synthetic profiles/interactions. Distinguish development, fixed evaluation, and
sequential cases. Document researcher decision annotations and their limitations.

## Architecture
Explain Planner, Coach, Reviewer, single-agent baseline, temporal tools, SQLite
memory, explicit preference precedence, skill procedures, and resource provenance.
Define one planning round and one review/revision cycle. Explain early stopping.

## Experimental protocol
List models/providers, settings, prompts, hardware, dates, input hashes, versions,
repeat count, and all ablations. Keep inputs and tools constant. Describe human
blinding and shared judge rubric. Report judge failures and rating denominators.

## Results
Insert generated tables/figures for decision appropriateness, message quality,
execution success, decision frequencies, actual depths, calls, tokens, and latency.
Report human and LLM scores, per-dimension/overall MAE, and concrete disagreements.
Compare required ablations and model choices; do not invent missing values.

## Discussion
Explain where additional rounds helped or wasted computation, failure modes,
missing data behavior, memory updates, and whether the final configuration differs
from the reference. Final configuration retains at least two agents.

## Limitations
Small historical cohort; simulated preferences/feedback; uncertain sensing coverage;
subjective annotations and judge bias; no demonstrated intervention effectiveness;
provider variability. Distinguish case-level repetition from independent participants.

## Reproducibility
Document exact commands, environment, memory reset, frozen inputs, outputs, and logs.
