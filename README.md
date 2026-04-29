# Northwind Triage Agent

Triage agent + LLM-as-judge evaluator for Northwind Home Services inbound messages.

For the design write-up, prompts, and evaluation findings see [`WRITEUP.md`](WRITEUP.md).

---

## Setup

**1. Bring an Anthropic API key.**

```bash
cp .env.example .env
# then edit .env and set ANTHROPIC_API_KEY=<your-key>
```

**2. Install dependencies with uv.**

```bash
uv sync
```

**3. Activate the virtualenv.**

```bash
source .venv/bin/activate
```

---

## Run

Four commands. All run from the project root.

**Run the agent on one hardcoded message (smoke test, MSG-001):**

```bash
python -m src.agent
```

**Run the evaluator on one message (triage + deterministic score + LLM judge, MSG-001):**

```bash
python -m src.evaluator
```

**Run the agent on all 20 inbound messages and save decisions to `outputs/agent_result.json`:**

```bash
python -m scripts.run_agent
```

**Run the full evaluation on all 20 messages and save the report to `outputs/evaluation_report.json`:**

```bash
python -m scripts.run_evaluator
```

---

## Outputs

The `outputs/` folder contains the results from the latest full run on all 20 messages:

- `outputs/agent_result.json`: agent decisions for all 20 messages.
- `outputs/evaluation_report.json`: evaluator results and scores for all 20 messages.

---

## Approximate Runtime

- Single agent run on one message: 15-20 seconds.
- Single evaluator run on one message: 12-17 seconds.
- Agent run on all 20 messages: 3-4 minutes.
- Full evaluation run on all 20 messages: 8-10 minutes.
