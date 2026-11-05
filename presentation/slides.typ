#import "@preview/touying:0.8.0": config-page, themes
#import themes.simple: simple-theme, slide
#import "theme.typ": *

#let evidence = json("assets/project_results.json")
#let rows = evidence.rows
#let full = rows.at(0)

#show: simple-theme.with(
  aspect-ratio: "16-9",
  primary: ink,
  header: none,
  header-right: none,
  footer: none,
  footer-right: context [#text(size: page-number-size, fill: page-number-fill)[
    #counter(page).display() / #counter(page).final().first()
  ]],
  subslide-preamble: none,
  config-page(width: 960pt, height: 540pt, margin: (bottom: slide-margin, rest: slide-margin), fill: cream),
)
#show: apply-theme.with()
#set document(title: "StudentLife Stress Coach", author: ("Mahdi Moghaddami", "Brett Piggott"))
#set par(leading: 0.65em)
#set list(spacing: 0.85em)
#set enum(spacing: 0.65em)

#let source(body) = text(size: 11pt, fill: ink2, body)
#let label(body, color: olive) = text(font: heading-font, size: 23pt, weight: "bold", fill: color, body)
#let node(x, y, w, h, body, agent: false, dark: false) = place(dx: x, dy: y, rect(
  width: w,
  height: h,
  radius: if agent { 8pt } else { 0pt },
  fill: if dark { olive } else { cream },
  stroke: 1.5pt + olive,
  inset: 7pt,
  align(center + horizon, {
    set par(leading: 0.35em)
    text(size: 16pt, fill: if dark { cream } else { ink }, body)
  }),
))
#let hline(x, y, w, color: olive, dash: false) = place(dx: x, dy: y, line(length: w, stroke: (
  paint: color,
  thickness: 1.6pt,
  dash: if dash { "dashed" } else { "solid" },
)))
#let vline(x, y, h, color: olive, dash: false) = place(dx: x, dy: y, line(angle: 90deg, length: h, stroke: (
  paint: color,
  thickness: 1.6pt,
  dash: if dash { "dashed" } else { "solid" },
)))
#let right-arrow(x, y, w, color: olive) = {
  hline(x, y, w, color: color)
  place(dx: x + w - 7pt, dy: y - 4pt, polygon((0pt, 0pt), (7pt, 4pt), (0pt, 8pt), fill: color, stroke: none))
}
#let left-arrow(x, y, w, color: olive) = {
  hline(x, y, w, color: color)
  place(dx: x, dy: y - 4pt, polygon((7pt, 0pt), (0pt, 4pt), (7pt, 8pt), fill: color, stroke: none))
}
#let down-arrow(x, y, h, color: olive) = {
  vline(x, y, h, color: color)
  place(dx: x - 4pt, dy: y + h - 7pt, polygon((0pt, 0pt), (4pt, 7pt), (8pt, 0pt), fill: color, stroke: none))
}
#let up-arrow(x, y, h, color: olive) = {
  vline(x, y, h, color: color)
  place(dx: x - 4pt, dy: y, polygon((0pt, 7pt), (4pt, 0pt), (8pt, 7pt), fill: color, stroke: none))
}
#let diagram-label(x, y, body, w: 100pt) = place(dx: x, dy: y, block(width: w, fill: cream, inset: 1pt, text(
  size: 13pt,
  fill: ink2,
  body,
)))

// Main talk: slides 1-8, approximately five minutes.
#slide(config: config-page(fill: olive, footer: none))[
  #set text(fill: cream)
  #block(width: 896pt, height: 470pt)[
    #place(top + right, text(size: 12pt)[November 5, 2026])
    #place(dy: 90pt, text(font: heading-font, size: 76pt)[StudentLife\ Stress Coach])
    #place(dy: 310pt, text(size: 24pt)[Personalized support with language agents])
    #place(dy: 403pt, text(size: 20pt)[Mahdi Moghaddami and Brett Piggott])
    #place(dy: 435pt, text(size: 14pt)[CSI 4900/5900 Agentic AI, Oakland University])
    #place(dy: 461pt, line(length: 100%, stroke: 0.6pt + cream))
  ]
]

#split-slide(
  36%,
  [
    #slide-title([The coaching\ task], color: cream)
    #v(38pt)
    #text(font: heading-font, size: 37pt)[Suggest\ Ask\ Stay silent]
    #v(1fr)
    #text(size: 20pt)[A useful message must fit the student's situation and preferences.]
  ],
  [
    #label[StudentLife observations]
    #v(10pt)
    #text(size: 21pt)[
      - Inferred sleep, activity and social indicators
      - EMA stress and mood
      - Academic schedules and deadlines
      - Pre-term survey background
    ]
    #v(20pt)
    #label[Clearly labeled simulation]
    #v(8pt)
    #text(size: 21pt)[Goals, coaching preferences and scripted feedback fill information the dataset does not contain.]
    #v(20pt)
    #text(font: heading-font, size: 30pt, fill: olive)[20 cases across 8 participants]
    #v(10pt)
    #source[49 identifiers in the supplied activity archive. The published study describes 48 students over ten weeks.]
  ],
)

#slide[
  #slide-title[Five interacting roles]
  #v(13pt)
  #block(width: 896pt, height: 367pt)[
    // Data flow and agent exchanges, drawn as editable Typst objects.
    #right-arrow(160pt, 60pt, 60pt)
    #right-arrow(370pt, 48pt, 60pt)
    #left-arrow(370pt, 78pt, 60pt)
    #right-arrow(585pt, 48pt, 65pt)
    #left-arrow(585pt, 78pt, 65pt)
    #down-arrow(507pt, 95pt, 78pt)
    #vline(295pt, 95pt, 110pt)
    #right-arrow(295pt, 205pt, 135pt)
    #right-arrow(585pt, 205pt, 65pt)
    #vline(745pt, 235pt, 35pt, color: orange)
    #hline(507pt, 270pt, 238pt, color: orange)
    #up-arrow(507pt, 235pt, 35pt, color: orange)
    #hline(840pt, 205pt, 35pt)
    #vline(875pt, 205pt, 112pt)
    #left-arrow(840pt, 317pt, 35pt)
    #left-arrow(370pt, 317pt, 280pt)
    #hline(80pt, 317pt, 140pt)
    #up-arrow(80pt, 235pt, 82pt)
    #up-arrow(80pt, 95pt, 78pt)
    #node(0pt, 25pt, 160pt, 70pt, [Case snapshot\ student + time\ observations])
    #node(
      220pt,
      25pt,
      150pt,
      70pt,
      [#text(weight: "bold", fill: cream)[Planner]\ choose checks\ and action],
      agent: true,
      dark: true,
    )
    #node(
      430pt,
      25pt,
      155pt,
      70pt,
      [#text(weight: "bold", fill: cream)[Context Analyst]\ collect findings],
      agent: true,
      dark: true,
    )
    #node(650pt, 25pt, 190pt, 70pt, [Read-only tools\ sensing, EMA,\ academic, resources])
    #node(0pt, 173pt, 160pt, 62pt, [Student memory\ profile, episodes,\ learned rules])
    #node(
      430pt,
      173pt,
      155pt,
      62pt,
      [#text(weight: "bold", fill: cream)[Message Writer]\ draft with a skill],
      agent: true,
      dark: true,
    )
    #node(
      650pt,
      173pt,
      190pt,
      62pt,
      [#text(weight: "bold", fill: cream)[Critic]\ check and request\ a revision],
      agent: true,
      dark: true,
    )
    #node(
      220pt,
      285pt,
      150pt,
      65pt,
      [#text(weight: "bold", fill: cream)[Memory Manager]\ extract rules\ from feedback],
      agent: true,
      dark: true,
    )
    #node(650pt, 285pt, 190pt, 65pt, [Final coaching action\ suggest / ask / none])
    #diagram-label(371pt, 28pt, [checks], w: 58pt)
    #diagram-label(371pt, 84pt, [findings], w: 58pt)
    #diagram-label(587pt, 28pt, [query], w: 60pt)
    #diagram-label(587pt, 84pt, [result], w: 60pt)
    #diagram-label(309pt, 181pt, [strategy], w: 110pt)
    #diagram-label(511pt, 129pt, [evidence], w: 90pt)
    #diagram-label(588pt, 181pt, [draft], w: 60pt)
    #diagram-label(538pt, 253pt, [revise within budget], w: 182pt)
    #diagram-label(754pt, 252pt, [pass / budget ends], w: 121pt)
    #diagram-label(386pt, 293pt, [SIMULATED feedback, if available], w: 256pt)
    #diagram-label(10pt, 270pt, [persist episode + rules], w: 185pt)
    #diagram-label(5pt, 128pt, [prior context only], w: 152pt)
  ]
  #v(8pt)
  #source[Simplified full configuration. Silence bypasses writing/review. Feedback follows the action. JSONL serialization includes the memory update.]
]

#slide[
  #slide-title[Five required design patterns]
  #v(20pt)
  #set text(size: 21pt)
  #set table(inset: (x: 10pt, y: 12pt), stroke: none)
  #table(
    columns: (205pt, 1fr),
    align: left,
    table.hline(stroke: 1.2pt + olive),
    [*Reflection*], [Critic reviews the draft and requests revisions. Maximum 2 cycles.],
    [*Tool use*], [Analyst chooses data queries. Writer can load a coaching skill.],
    [*Planning*], [Planner selects evidence checks and the action. Maximum 2 calls.],
    [*Multi-agent system*], [Five roles exchange structured, validated outputs.],
    [*Memory and skills*], [JSON history and learned rules, plus 8 reusable Markdown procedures.],
    table.hline(stroke: 1.2pt + olive),
  )
  #v(20pt)
  #text(size: 19pt)[Full system: Gemini 3.6 Flash. Independent judge: OpenAI GPT-5.4 mini.]
  #v(8pt)
  #source[All patterns can be switched or varied in TOML. Full retains five recent episodes and prior rules. No training or fine-tuning.]
]

#split-slide(
  36%,
  [
    #slide-title([Memory across\ interactions], color: cream)
    #v(28pt)
    #text(size: 20pt)[#text(weight: "bold", fill: cream)[Student u16]]
    #v(12pt)
    #text(
      size: 19pt,
    )[#text(weight: "bold", fill: cream)[April 15]\ Simulated reply prefers quiet breathing, stretching or tea.]
    #v(18pt)
    #text(
      size: 19pt,
    )[#text(weight: "bold", fill: cream)[April 18]\ New simulated feedback requests library-compatible messages under 35 words.]
    #v(18pt)
    #text(size: 19pt)[#text(weight: "bold", fill: cream)[April 22]\ The next interaction can use both earlier updates.]
  ],
  [
    #label[April 22: a deadline and reported stress]
    #v(18pt)
    #text(size: 20pt)[The coach selects #text(font: mono-font, size: 17pt)[micro_study_break].]
    #v(20pt)
    #line(length: 100%, stroke: 1.2pt + orange)
    #v(20pt)
    #text(font: heading-font, size: 28pt)[“#evidence.example.message”]
    #v(18pt)
    #text(size: 18pt, fill: olive)[#evidence.example.words words. Quiet, desk-compatible support.]
    #v(18pt)
    #source[Actual full-system output, case_015. Profile preferences and replies are simulated. The baseline already favors quiet breaks, so this example does not isolate a causal memory benefit.]
  ],
)

#slide[
  #slide-title[Full-system results]
  #v(10pt)
  #block(width: 896pt, height: 395pt)[
    #place(dy: 0pt, text(size: 20pt)[Human rates 10 messages before seeing the independent judge's scores.])
    #place(dy: 55pt, text(font: heading-font, size: 50pt, fill: olive)[20 / 20])
    #place(dy: 112pt, text(size: 18pt)[Agreement with allowed actions])
    #place(dy: 170pt, text(font: heading-font, size: 50pt, fill: olive)[4.81 / 5])
    #place(dy: 227pt, text(size: 18pt)[Mean quality across 16 messages])
    #place(dy: 277pt, block(width: 345pt, text(size: 19pt)[13 suggestions, 3 questions,\ 4 silent decisions.]))
    #place(dx: 405pt, dy: 55pt, label[Human and LLM scores])
    #place(dx: 405pt, dy: 100pt, block(width: 491pt)[
      #set text(size: 19pt)
      #set table(inset: (x: 7pt, y: 7pt), stroke: none)
      #table(
        columns: (1fr, auto, auto),
        align: (left, right, right),
        table.hline(stroke: 1pt + olive),
        [Criterion], [Human], [Judge],
        table.hline(stroke: 0.5pt + olive),
        [Context awareness], [4.70], [4.80],
        [Goal alignment], [4.80], [4.90],
        [Clarity], [5.00], [4.60],
        table.hline(stroke: 1pt + olive),
      )
    ])
    #place(dx: 405pt, dy: 247pt, text(font: heading-font, size: 27pt, fill: olive)[0.267 mean absolute difference])
    #place(dx: 405pt, dy: 290pt, text(size: 17pt)[30 criterion ratings. Largest gap: clarity.])
    #place(dy: 337pt, text(size: 20pt)[*Mean efficiency:* 35.59 seconds, 6.20 LLM calls, 17,529 tokens per case.])
    #place(
      dy: 377pt,
      source[Rubric: context awareness, goal alignment, clarity (1-5). Silence has no quality score. Latency includes coaching/tools and excludes judging.],
    )
  ]
]

#slide[
  #slide-title[Planning and reflection budgets]
  #v(8pt)
  #block(width: 896pt, height: 414pt)[
    #place(top + center, image("assets/report-depth-tradeoffs.svg", width: 896pt, height: 308pt, fit: "contain"))
    #place(dy: 316pt, text(size: 19pt)[Reflection maxima 1-3 each execute one review per message on average.])
    #place(dy: 347pt, text(size: 17pt)[Single coach: 4.81 quality, 3.65 calls. Model B: 4.89 quality, 19/20 allowed actions.])
    #place(dy: 380pt, source[Report, Figure 3. Tokens use the right axes. Planning agreement is percent / 20 (100% = 5). Quality cohorts contain 15-16 messages; one generation per condition.])
  ]
]

#slide(config: config-page(fill: orange, footer: none))[
  #set text(fill: cream)
  #slide-title([Conclusions], color: cream)
  #v(38pt)
  #text(font: heading-font, size: 34pt)[Five roles make plans, evidence and remembered preferences inspectable.]
  #v(30pt)
  #text(size: 25pt)[More roles and larger budgets did not consistently improve message quality.]
  #v(28pt)
  #text(
    size: 23pt,
  )[Small offline benchmark, simulated goals and feedback, and one human rater. We do not measure changes in student stress.]
  #v(1fr)
  #line(length: 100%, stroke: 0.6pt + cream)
  #v(12pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 30pt,
    [#text(
      size: 16pt,
    )[#text(weight: "bold", fill: cream)[Mahdi Moghaddami]\ Data, tools, orchestration and experiments. Human ratings.]],
    [#text(
      size: 16pt,
    )[#text(weight: "bold", fill: cream)[Brett Piggott]\ Writing/critique, memory, skills and automated evaluation. Figures and report.]],
  )
]

// Backup slides for questions.
#slide[
  #slide-title[Appendix: all nine conditions]
  #v(18pt)
  #set text(size: 19pt)
  #set table(inset: (x: 10pt, y: 8pt), stroke: none)
  #table(
    columns: (1.6fr, 0.8fr, 0.9fr, 0.8fr, 0.9fr, 0.9fr),
    align: left,
    table.hline(stroke: 1pt + olive),
    [*Configuration*], [*Quality*], [*Agreement*], [*Calls*], [*Tokens (k)*], [*Latency (s)*],
    table.hline(stroke: 0.5pt + olive),
    ..rows
      .map(r => (
        text(weight: if r.id == "full" { "bold" } else { "regular" }, r.label),
        str(r.quality),
        [#r.agreement%],
        str(r.calls),
        str(calc.round(r.tokens / 1000, digits: 2)),
        str(r.latency),
      ))
      .flatten(),
    table.hline(stroke: 1pt + olive),
  )
  #v(22pt)
  #text(
    size: 19pt,
  )[*Depth finding:* reflection maxima 1, 2 and 3 each execute one review per sent message on average. Actual Planner calls average 1, 2 and 2.05 at maxima 1, 2 and 3.]
  #v(14pt)
  #source[All values are means. Conditional quality cohorts contain 15-16 messages. Latency includes provider waits and recovery work. Each condition has its own evolving history.]
]

#slide[
  #slide-title[Appendix: tools and coaching skills]
  #v(18pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 36pt,
    [
      #label[Eight data and resource tools]
      #v(15pt)
      #set text(font: mono-font, size: 17pt)
      #set list(spacing: 0.75em)
      - get_time_context
      - get_sleep_summary
      - get_activity_summary
      - get_social_summary
      - get_stress_mood_history
      - get_academic_load
      - compare_to_baseline
      - search_campus_resources
      #v(15pt)
      #text(
        font: body-font,
        size: 17pt,
      )[Writer: #text(font: mono-font)[load_skill]. Single coach also has #text(font: mono-font)[recall_memory].]
    ],
    [
      #label[Eight reusable skill procedures]
      #v(15pt)
      #set text(font: mono-font, size: 17pt)
      #set list(spacing: 0.75em)
      - micro_study_break
      - sleep_hygiene_nudge
      - gentle_movement
      - social_reconnection
      - deadline_chunking
      - campus_resource_referral
      - clarifying_question
      - positive_reinforcement
      #v(15pt)
      #text(
        font: body-font,
        size: 17pt,
      )[Skill files provide applicability guidance, constraints and writing instructions.]
    ],
  )
  #v(20pt)
  #source[Data tools expose bounded observations and explicit missing-data status. Campus resources are manually curated. Tool windows default to three days where applicable.]
]

#slide[
  #slide-title[Appendix: models, input and output]
  #v(20pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 40pt,
    [
      #block(width: 100%, height: 392pt)[
        #place(dy: 0pt, label[Exact model settings])
        #place(dy: 45pt, text(size: 18pt)[*Model A: full and structural ablations*])
        #place(dy: 73pt, text(font: mono-font, size: 15pt)[gemini:gemini-3.6-flash])
        #place(dy: 100pt, text(size: 17pt)[Temperature 0.3, Critic/Memory Manager 0.1.\ Thinking low. 8,192 output tokens.])
        #place(dy: 170pt, text(size: 18pt)[*Model B: same full architecture*])
        #place(dy: 198pt, text(font: mono-font, size: 15pt)[gemini:gemini-3.5-flash-lite])
        #place(dy: 225pt, text(size: 17pt)[Same role temperatures and output cap.])
        #place(dy: 282pt, text(size: 18pt)[*Independent judge*])
        #place(dy: 310pt, text(font: mono-font, size: 15pt)[openai:gpt-5.4-mini-2026-03-17])
        #place(dy: 342pt, text(size: 17pt)[Temperature 0, reasoning none.\ 2,048 completion tokens.])
      ]
    ],
    [
      #label[Participant at a decision time]
      #v(12pt)
      #text(
        size: 18pt,
      )[Input: observations available by that time, a simulated profile, and strictly earlier interactions.]
      #v(20pt)
      #label[One final JSONL record per case]
      #v(10pt)
      #set text(font: mono-font, size: 14pt)
      #raw(
        json.encode(
          (
            case_id: evidence.example.record.case_id,
            participant_id: evidence.example.record.participant_id,
            decision: evidence.example.record.decision,
            skill_used: evidence.example.record.skill_used,
            trace: evidence.example.trace,
          ),
          pretty: true,
        ),
        lang: "json",
        block: true,
      )
      #v(12pt)
      #text(
        font: body-font,
        size: 17pt,
      )[Projected actual record. Full output also stores evidence, frozen context, plans, critiques and memory updates.]
    ],
  )
]


#slide[
  #slide-title[Report workflow: context and planning]
  #v(10pt)
  #align(center)[#image("assets/report-workflow-planning.svg", width: 896pt, height: 315pt, fit: "contain")]
  #v(15pt)
  #text(size: 21pt)[The bounded view combines observations with the student's profile and earlier history.]
  #v(12pt)
  #source[Report, Figure 1, upper section. Original vector artwork, enlarged as an excerpt. Planning and tool queries use observations available at the decision time.]
]

#slide[
  #slide-title[Report workflow: independent evaluation]
  #v(10pt)
  #align(center)[#image("assets/report-workflow-evaluation.svg", width: 896pt, height: 315pt, fit: "contain")]
  #v(15pt)
  #text(size: 21pt)[Judge scores non-null messages. All cases contribute execution and efficiency metrics.]
  #v(12pt)
  #source[Report, Figure 2. Original vector artwork. Offline evaluation is excluded from coaching latency.]
]
