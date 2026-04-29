# Northwind Triage Agent — Take-Home Submission

## Agent Design

A **single LangChain chain** wrapping Claude Sonnet 4.5 with structured output bound to a Pydantic schema. One message in, one `TriageDecision` out. No graph, no multi-agent orchestration, no retrieval.

The reference documents (SOP, catalogue, tone guide) are embedded verbatim in the system prompt — they total ~3k tokens, so retrieval would be ceremony. The schema includes a structured `Reasoning` sub-model with three fields (`rules_applied`, `judgement_calls`, `summary`) that explicitly separates rule-application from judgement, mirroring the rubric's interest in "clear separation between rule-following and judgement." A separate LLM-as-judge evaluator runs on the same 20 messages for the qualitative checks the rubric requires (draft and reasoning quality).

Out-of-hours detection is computed in Python from `received_at` and injected into the model's input — LLMs are unreliable at parsing ISO timestamps into day-of-week, so this is deterministic rather than left to model reasoning.

I considered LangGraph, Deep Agents, and a multi-call pipeline (classify → priority → route → draft) and rejected all of them: the sub-decisions are tightly coupled, splitting them across nodes would either duplicate context across many calls or lose information between steps. A single well-prompted call wins on this scale.

The triage agent is a single-shot structured-output classifier that converts one inbound customer message into one `TriageDecision`. The decision contract is enforced as a Pydantic schema (`src/schemas.py`): a `category` enum (`BOOKING | QUOTE | COMPLAINT | EMERGENCY | BILLING | OUT_OF_SCOPE`), a `priority` enum (`P1 | P2 | P3`), a `route_to` list of teams, a `draft_reply`, a `needs_human_review` flag, and a nested `reasoning` object that splits the agent's logic into `rules_applied` (deterministic SOP/catalogue lookups), `judgement_calls` (places where rules ran out and the agent had to interpret), and a plain-English `summary`. The model is `claude-sonnet-4-5` invoked via LangChain's `ChatAnthropic.with_structured_output(TriageDecision, include_raw=True)`, so the schema is enforced at the tool-call layer rather than reconstructed from free-form text.

The shape is deliberately not agentic. The task is bounded — a fixed reference corpus (SOP, catalogue, tone guide) plus a closed enum decision space — so giving the model tools or memory would add latency and failure modes without unlocking new behaviour. Instead the entire reference corpus is injected into the system prompt once, and a numbered decision procedure walks the model through the same steps a human triager would follow (OUT_OF_SCOPE check first, then category in priority order, then priority, then routing, then human-review flag, then draft, then reasoning). Splitting reasoning into `rules_applied` vs. `judgement_calls` is the load-bearing design choice: it lets a human reviewer tell at a glance whether a decision came from a rule or from interpretation, which is exactly the information needed to decide whether to trust the output or override it.

---

## Final Prompts

Two prompts in `src/prompts.py`:

**`SYSTEM_PROMPT`** — the triage agent. Embeds SOP/catalogue/tone guide verbatim, adds a role frame, an 8-step decision procedure, instructions on `rules_applied` vs `judgement_calls`, and the distinction between `judgement_calls` (descriptive — where I interpreted) and `needs_human_review` (routing — driven by SOP §6 triggers).

**`JUDGE_SYSTEM_PROMPT`** — the LLM-as-judge for qualitative scoring. Embeds the tone guide, instructs the judge to assess draft must-include/must-not-include items semantically (not by string match), to score tone against the guide, and to assess reasoning quality (right rules, correct ambiguity surfacing, no bluffing).

Both files are in the repo. Token count: system prompt ~3k tokens, well under context budget.

Both are f-strings that inline the markdown reference docs from `data/reference/` (`sop.md`, `catalogue.md`, `tone_guide.md`) at module import.

### Agent system prompt (`SYSTEM_PROMPT`)

Used by `triage()` in `src/agent.py`. Establishes the agent's role, embeds the three reference documents as the source of truth, and prescribes an explicit decision procedure plus reasoning conventions.

```text
# Role
You are the first-pass triage agent for Northwind Home Services, a residential
trades business in Sydney. You receive customer messages from email, SMS, and
webform, and produce a structured triage decision that a human dispatcher
reviews before action.

The three documents below are your source of truth. Do not invent rules that
are not in them.

---
# Standard Operating Procedure
{SOP}                    # injected from data/reference/sop.md

---
# Service Catalogue
{CATALOGUE}              # injected from data/reference/catalogue.md

---
# Tone & Style Guide
{TONE_GUIDE}             # injected from data/reference/tone_guide.md

---
# Decision Procedure
Walk through these steps in order for every message:

1. Read the message fully. Note: sender, channel, time of day, what they're
   asking for, whether they are upset, whether the language is English, whether
   the content is coherent.
2. Check OUT_OF_SCOPE first. If the request matches anything in the catalogue's
   "Things we do not do" section, classify as OUT_OF_SCOPE.
3. Classify the category per SOP Section 2. Check in this order:
   EMERGENCY → COMPLAINT → BILLING → QUOTE → BOOKING. If torn between QUOTE and
   BOOKING, default to QUOTE.
4. Set the priority per SOP Section 3. EMERGENCY is always P1. Apply special
   rules from SOP Section 4 (e.g. HVAC has no on-call → after-hours HVAC is P2).
5. Route per SOP Section 4. Output is a list of teams. Single team in most cases; 
   multiple teams only when SOP Section 4's special-case rules explicitly require it. 
   Look up the specific cases there rather than guessing.
6. Decide needs_human_review per SOP Section 6. Use catalogue prices to
   estimate whether quote thresholds are crossed.
7. Draft the reply per the tone guide. Match the customer's situation
   (upset / emergency / out-of-scope / non-English / garbled).
8. Populate reasoning as described below.

---
# How to Reason
- rules_applied — always populate. Cite specific rules with their source.
  If you cannot cite a rule, you are guessing.
- judgement_calls — populate ONLY when rules conflict, are ambiguous, don't
  cover the case, or multiple defensible answers exist. Otherwise leave [].
  Do not invent ambiguity.
- summary — always populate. 1–3 sentences in plain English.

---
# needs_human_review vs judgement_calls
These are independent. needs_human_review is routing (driven by SOP §6's
explicit list). judgement_calls is descriptive (driven by rules running out).
A case can be flagged without judgement (non-English: SOP says flag, no
interpretation needed). A case can require judgement without being flagged.
```

### LLM-as-judge system prompt (`JUDGE_SYSTEM_PROMPT`)

Used by `judge()` in `src/evaluator.py` to score the qualitative dimensions (draft reply quality, reasoning quality) that can't be checked with `==`. Outputs a `JudgeVerdict` (`src/schemas.py`).

```text
# Role
You are a qualitative evaluator for a customer-service triage agent at
Northwind Home Services. The agent has classified an inbound customer message
and produced a draft reply plus reasoning. Your job is to assess two things
the rubric flags as qualitative (judgement-based, not numeric):

1. Draft reply quality — does it hit the points the benchmark says it must
   include, avoid the points it must not include, and sound like the Northwind
   tone guide rather than a generic LLM voice?
2. Reasoning quality — does the agent's reasoning weigh the right rules, or
   is it bluffing past ambiguity?

You are NOT scoring the four hard fields (category, priority, route_to,
needs_human_review). Those are scored deterministically elsewhere.

---
# How to Judge Draft Reply Quality
- For each must_include item: judge whether the draft semantically covers it.
  Look at meaning, not strings.
- For each must_not_include item: judge whether the draft violates it.
- Tone: Northwind sounds like a competent neighbour, not a call centre.
  Common failure modes: generic openers, over-apologising, "rest assured",
  exclamation marks, promising specific times, quoting "from $X" prices,
  naming a tradesperson, replies longer than 2–4 sentences.

---
# How to Judge Reasoning Quality
- Did the agent cite the right rules for the case (the ones that actually
  drive the decision, not just any rules)?
- Did the agent correctly identify ambiguity? If the benchmark notes flag
  the case as ambiguous, did the agent surface it in judgement_calls — or
  did it confidently bluff past it?
- Did the agent invent ambiguity where none existed?
- Is the summary accurate and grounded, or hand-wavy?

---
# Output Style
Produce a structured JudgeVerdict:
- per-item flags on must_include / must_not_include
- tone: "matches" | "drifts" | "off"
- reasoning_assessment: "sound" | "shaky" | "bluffing"
- short evidence quotes when flagging issues
- 1–2 sentence overall_verdict

Always populate every field. Do not be lenient — the point is to find drift
and weak spots, not to validate the agent.

---
# Tone & Style Guide (Reference)
{TONE_GUIDE}             # same tone guide given to the agent
```

---

## Headline Accuracy

**Strict accuracy: 70%** (14 of 20 messages matched on all four hard fields).

**Per-field accuracy:**
- `category`: 95%
- `priority`: 95%
- `route_to`: 98%
- `needs_human_review`: 85%

The agent is strongest on category and routing, weakest on flagging for human review. Most strict failures came from `needs_human_review` calls where the SOP rules ran out and judgement was required.

---

## 3 Cases Where I Disagree With the Benchmark

**Case 1: MSG-007 (Dishwasher repair)**
- Benchmark: `needs_human_review: true`
- Agent: `needs_human_review: false`
- Reason: Catalogue is explicit ("we install but do not repair appliances"). None of SOP §6's flag triggers apply. Benchmark flags on a soft "human might add value" basis the SOP doesn't encode. Agent's strict reading is correct.

**Case 2: MSG-008 (Bathroom reno plumbing)**
- Benchmark: `needs_human_review: true`
- Agent: `needs_human_review: false`
- Reason: Catalogue lists this at "from $4,500" — under SOP §6's $5,000 flag threshold. Benchmark flags based on speculation that the actual quote *might* exceed $5k. Benchmark's own notes say "defensible to leave false if you read it strictly."

**Case 3: MSG-019 (Catherine's refund follow-up)**
- Benchmark: `priority: P2`
- Agent: `priority: P3`
- Reason: Customer is polite, no anger, no threats. SOP §3 defines P2 as essential function loss or complaint over $1,000 — neither applies here. Benchmark went P2 on "financial impact" reasoning that's not in the SOP. Benchmark itself notes "defensible as P3."

**Pattern:** All three are cases where the SOP itself is under-specified and the benchmark fills the gaps with practical judgement an automated agent reasonably wouldn't replicate. These are SOP gaps, not agent failures — and worth flagging back to Northwind as places the SOP needs tightening.

---

## 3 Cases Where the Agent Failed

**Failure 1: MSG-016 (Olivia's combined quote)**
- What went wrong: Catalogue lists ducted aircon at "from $9,500" — over the $5,000 threshold. Agent should have flagged. Also promised a single combined site visit when catalogue requires separate assessment for ducted aircon.
- Why: Two reasons. First, prompt issue — my prompt doesn't explicitly tell the agent to compare catalogue "from" prices against the $5k threshold or surface conflicts when one customer request spans multiple services. Second, LLMs are weak at numerical comparison — even "$9,500 > $5,000" can fail under load. A simple deterministic maths tool (`compare_to_threshold(price, threshold)`) would make this exact and auditable.

**Failure 2: MSG-013 (Garbled "asdf asdf test test")**
- Benchmark says agent should flag and skip drafting; my agent produced a polished placeholder reply.
- Why per benchmark: Schema forces `draft_reply: str`, so the agent can't return "no draft."
- My push-back: I'd argue this isn't a real failure. The agent's reply ("we couldn't make out what you need, send more detail") is honest, brief, and gives a real user a path forward in case it was an accidental submission. We didn't pretend to understand. By the benchmark's strict letter it's a fail; by sensible operations it's fine.

**Failure 3: Out-of-hours rules ignored across multiple messages**
- What went wrong: Agent promised same-day responses on messages received after hours or on weekends, despite SOP §7 saying P2/P3 should queue for next business morning.
- Why: Agent doesn't know current date/day/time. LLMs are unreliable at parsing ISO timestamps into day-of-week.
- Fix: Added Python-side parsing in `_format_message` to inject "Saturday 22:30, Out-of-hours: YES" directly. Deterministic, no model guessing.

---

## Tone

The agent's draft voice was mostly consistent with the tone guide — plain language, customer first names, no generic openers, no exclamation marks, correct sign-off on the majority of messages. Where it drifted was on the harder cases: complaints, ambiguous scope, garbled input. On those it reached for corporate-safe phrasing (performative apologies, hedging words like "definitely", specific times instead of windows) — the opposite of what the tone guide wants ("honest, not performative"). The pattern suggests the agent does well on cases that mirror the tone guide's own examples and drifts where the guide doesn't directly demonstrate the voice.

---

## SOP / Catalogue / Tone Guide Contradictions Spotted

A few places where the source documents don't fully agree:

- **SOP §6 says flag quotes "over $5,000"**, but the catalogue lists bathroom reno plumbing at "from $4,500" — common bathroom renos exceed $5k in practice, creating ambiguity over whether to flag based on the catalogue floor or the likely actual amount. The benchmark and SOP take different sides on this.
- **SOP §3 lists P2 thresholds as "complaints involving a charge over $1,000"**, but the tone guide instructs you to acknowledge upset customers directly regardless of priority. This creates tension on cases like MSG-017 (conduct complaint, $280 job) — the SOP says P3 by amount, but the upset-customer signal pushes toward P2.
- **SOP §2 names "no hot water in winter" as P1 EMERGENCY**, but says nothing about analogous heating failures. SOP §4 then explicitly says HVAC has no on-call. Together they imply heater-not-working is P2, but it requires reading two sections in conjunction — which trips both human and agent triagers.

---

## What I'd Build Next

Close the loop by sending the agent's drafts to customers and capturing what comes back.

Right now the agent produces drafts that go nowhere — there's no signal on whether they actually work in the wild. I'd wire up a FastAPI endpoint that sends approved drafts via email (Resend or similar), then track two things per message: did the customer reply, and if they did, was the reply something the agent could handle next or did it need a human to take over. That gives real production data on which drafts land and which don't — far more useful than the 20-message benchmark for finding what the agent actually gets wrong.
