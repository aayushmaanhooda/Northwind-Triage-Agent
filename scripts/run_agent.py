"""Run the triage agent across every inbound message and dump results."""

import json
from pathlib import Path

from src.agent import triage
from src.schemas import InboundMessage

INBOUND_PATH = Path("data/inbound_messages.json")
OUTPUT_PATH = Path("outputs/agent_result.json")


def main() -> None:
    payload = json.loads(INBOUND_PATH.read_text())
    messages = [InboundMessage(**m) for m in payload["messages"]]

    results = []
    for msg in messages:
        print(f"Triaging {msg.id}...")
        decision = triage(msg)
        results.append({"id": msg.id, "decision": decision.model_dump()})

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Wrote {len(results)} decisions to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
