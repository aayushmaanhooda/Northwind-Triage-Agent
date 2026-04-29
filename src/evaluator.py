"""Deterministic evaluator + LLM-as-judge for Northwind triage agent."""

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from dotenv import load_dotenv

from src.agent import triage
from src.schemas import InboundMessage, JudgeVerdict
from src.prompts import JUDGE_SYSTEM_PROMPT

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage


JUDGE_MODEL = "anthropic:claude-sonnet-4-6"

judge_model = init_chat_model(JUDGE_MODEL, temperature=0.5)
judge_chain = judge_model.with_structured_output(JudgeVerdict, include_raw=True)

_DATA_DIR = Path(__file__).parent.parent / "data"


# --- LLM-as-judge ---

def _format_judge_input(
    inbound_message: dict,
    decision: dict,
    benchmark: dict,
) -> str:
    """Build the human message for the judge: everything it needs to assess."""
    return f"""\
# Customer's original message

Channel: {inbound_message['channel']}
Subject: {inbound_message.get('subject') or '(none)'}

Body:
{inbound_message['body']}

---

# Agent's draft reply

{decision['draft_reply']}

---

# Benchmark draft requirements

Must include (semantically — not literal strings):
{chr(10).join(f"- {item}" for item in benchmark.get('draft_reply_must_include', []))}

Must NOT include:
{chr(10).join(f"- {item}" for item in benchmark.get('draft_reply_must_not_include', []))}

---

# Agent's reasoning

Rules applied:
{chr(10).join(f"- {r}" for r in decision['reasoning']['rules_applied'])}

Judgement calls:
{chr(10).join(f"- {j}" for j in decision['reasoning']['judgement_calls']) if decision['reasoning']['judgement_calls'] else "(none — agent reported no judgement was required)"}

Summary:
{decision['reasoning']['summary']}

---

# Benchmark notes (the gold-answer rationale)

{benchmark.get('notes', '(none)')}
"""


def judge(
    inbound_message: dict,
    decision: dict,
    benchmark: dict,
) -> dict:
    """Run the LLM-as-judge on one message. Returns a dict matching JudgeVerdict.

    Retries once on parse failure, then falls back to a default verdict so a
    single bad call doesn't abort the whole evaluation run.
    """
    messages = [
        SystemMessage(content=JUDGE_SYSTEM_PROMPT),
        HumanMessage(content=_format_judge_input(inbound_message, decision, benchmark)),
    ]
    last_error: object = None
    for _ in range(2):
        try:
            result = judge_chain.invoke(messages)
        except Exception as exc:
            last_error = exc
            continue
        parsed = result["parsed"]
        if parsed is not None:
            return parsed.model_dump()
        last_error = result.get("parsing_error")

    print(f"  WARN: judge failed after retry, using fallback verdict. Error: {last_error}")
    return JudgeVerdict().model_dump()


# --- Deterministic scoring ---
def score_route(agent_route: list[str], benchmark_route: str) -> float:
    """1.0 exact, 0.5 if primary team correct but cc missed, else 0.0."""
    benchmark_teams = [t.strip() for t in benchmark_route.split("+")]

    if set(agent_route) == set(benchmark_teams):
        return 1.0
    if benchmark_teams[0] in agent_route:
        return 0.5
    return 0.0


def evaluate(decision: dict, benchmark: dict) -> dict:
    """Score one decision against one benchmark entry on the 4 hard fields."""
    cat_score = 1.0 if decision["category"] == benchmark["category"] else 0.0
    pri_score = 1.0 if decision["priority"] == benchmark["priority"] else 0.0
    flag_score = 1.0 if decision["needs_human_review"] == benchmark["needs_human_review"] else 0.0
    route_score = score_route(decision["route_to"], benchmark["route_to"])

    strict = (
        cat_score == 1.0
        and pri_score == 1.0
        and route_score == 1.0
        and flag_score == 1.0
    )

    return {
        "id": benchmark["id"],
        "category": cat_score,
        "priority": pri_score,
        "route_to": route_score,
        "needs_human_review": flag_score,
        "strict_match": 1.0 if strict else 0.0,
    }


def format_accuracy(total: float, n: int) -> str:
    """Format an accuracy score with exactly two decimal places."""
    score = Decimal(str(total)) / Decimal(n)
    return str(score.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))


def aggregate(results: list[dict]) -> dict:
    """Compute strict accuracy and per-field accuracy across all messages."""
    n = len(results)
    return {
        "n_messages": n,
        "strict_accuracy": format_accuracy(sum(r["strict_match"] for r in results), n),
        "per_field_accuracy": {
            "category": format_accuracy(sum(r["category"] for r in results), n),
            "priority": format_accuracy(sum(r["priority"] for r in results), n),
            "route_to": format_accuracy(sum(r["route_to"] for r in results), n),
            "needs_human_review": format_accuracy(sum(r["needs_human_review"] for r in results), n),
        },
    }


# --- Report builder ---
def build_report(deterministic_results: list[dict], qualitative_results: list[dict]) -> dict:
    """Build the final report — only what the rubric asks for."""
    summary = aggregate(deterministic_results)

    per_message = []
    for det, qual in zip(deterministic_results, qualitative_results):
        per_message.append({
            "id": det["id"],
            "deterministic": {
                "category": det["category"],
                "priority": det["priority"],
                "route_to": det["route_to"],
                "needs_human_review": det["needs_human_review"],
                "strict_match": det["strict_match"],
            },
            "qualitative": {
                "draft_must_include": [
                    {"item": c["item"], "covered": c["covered"]}
                    for c in qual["must_include_checks"]
                ],
                "draft_must_not_include": [
                    {"item": c["item"], "violated": c["violated"]}
                    for c in qual["must_not_include_checks"]
                ],
                "tone": qual["tone"],
                "tone_notes": qual["tone_notes"],
                "reasoning_assessment": qual["reasoning_assessment"],
                "reasoning_notes": qual["reasoning_notes"],
                "overall_verdict": qual["overall_verdict"],
            },
        })

    return {"summary": summary, "per_message": per_message}


# --- Main: single-message smoke test (MSG-001) ---
if __name__ == "__main__":
    load_dotenv()

    inbound = json.loads((_DATA_DIR / "inbound_messages.json").read_text())
    benchmark = json.loads((_DATA_DIR / "benchmark.json").read_text())
    bench_by_id = {b["id"]: b for b in benchmark["decisions"]}

    raw = inbound["messages"][0]
    msg_id = raw["id"]
    bench = bench_by_id[msg_id]

    print(f"[{msg_id}] triaging...")
    decision = triage(InboundMessage(**raw)).model_dump()

    print(f"[{msg_id}] scoring deterministic fields...")
    det = evaluate(decision, bench)

    print(f"[{msg_id}] running judge...")
    qual = {"id": msg_id, **judge(raw, decision, bench)}

    report = build_report([det], [qual])
    print(json.dumps(report, indent=2, ensure_ascii=False))
