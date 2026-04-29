"""Run the evaluator across all 20 inbound messages and save the report."""

import json
from pathlib import Path

from dotenv import load_dotenv

from src.agent import triage
from src.evaluator import build_report, evaluate, judge
from src.schemas import InboundMessage

INBOUND_PATH = Path("data/inbound_messages.json")
BENCHMARK_PATH = Path("data/benchmark.json")
OUTPUT_PATH = Path("outputs/evaluation_report.json")


def main() -> None:
    load_dotenv()

    inbound = json.loads(INBOUND_PATH.read_text())
    benchmark = json.loads(BENCHMARK_PATH.read_text())
    bench_by_id = {b["id"]: b for b in benchmark["decisions"]}

    deterministic_results = []
    qualitative_results = []

    for raw in inbound["messages"]:
        msg_id = raw["id"]
        bench = bench_by_id[msg_id]

        print(f"[{msg_id}] triaging...")
        decision = triage(InboundMessage(**raw)).model_dump()

        print(f"[{msg_id}] scoring deterministic fields...")
        deterministic_results.append(evaluate(decision, bench))

        print(f"[{msg_id}] running judge...")
        qualitative_results.append({"id": msg_id, **judge(raw, decision, bench)})

    report = build_report(deterministic_results, qualitative_results)

    print("\n" + "=" * 60)
    print("Per-message strict matches")
    print("=" * 60)
    for det in deterministic_results:
        mark = "PASS" if det["strict_match"] == 1.0 else "FAIL"
        print(
            f"  [{mark}] {det['id']}  cat={det['category']}  pri={det['priority']}  "
            f"route={det['route_to']}  flag={det['needs_human_review']}"
        )

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved evaluation report to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
