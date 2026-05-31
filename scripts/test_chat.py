"""Drive the five PRD use cases (plus a memory follow-up) through /chat and
print the routed intent, streamed answer, and citations for each."""
from __future__ import annotations

import json
import sys

import httpx

API = "http://127.0.0.1:8000"
THREAD = "test-session-1"

QUESTIONS = [
    ("UC-1 (quantitative)", "What's the engagement rate of each?"),
    ("UC-2 (quantitative)", "Who's the creator of Video B and what's their follower count?"),
    ("UC-3 (qualitative)", "Compare the hooks in the first 5 seconds."),
    ("UC-4 (qualitative)", "Suggest improvements for B based on what worked in A."),
    ("UC-5 (hybrid)", "Why did Video A get more engagement than Video B?"),
    ("Follow-up (memory)", "Based on that, which video's style should I copy next time?"),
]


def ask(label: str, message: str) -> None:
    print(f"\n{'='*70}\n{label}\nQ: {message}\n{'-'*70}")
    intent = None
    citations = []
    answer_parts: list[str] = []

    with httpx.stream(
        "POST", f"{API}/chat",
        json={"message": message, "thread_id": THREAD}, timeout=120,
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            evt = json.loads(line[6:])
            t = evt.get("type")
            if t == "intent":
                intent = evt["intent"]
            elif t == "citations":
                citations = evt["citations"]
            elif t == "token":
                answer_parts.append(evt["content"])
                sys.stdout.write(evt["content"])
                sys.stdout.flush()
            elif t == "done":
                break

    print(f"\n{'-'*70}")
    print(f"ROUTED INTENT: {intent}")
    if citations:
        cites = ", ".join(
            f"[V{c['video_id']} chunk {c['chunk_id']} {c['modality']}]" for c in citations
        )
        print(f"CITATIONS: {cites}")
    else:
        print("CITATIONS: (none — quantitative path)")


def main() -> None:
    for label, q in QUESTIONS:
        ask(label, q)


if __name__ == "__main__":
    main()
