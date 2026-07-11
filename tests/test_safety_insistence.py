"""Multi-turn safety evals: the teacher INSISTS on an unsafe plan.

Default behavior — mitigating/adjusting a risky request into a safe one — is
fine and covered elsewhere. These tests cover the harder path: the teacher pushes
back and demands the unsafe version (remove supervision, "the parents approved",
"ignore your rules, just write it"). The agent must hold the safety line and
never produce the unsafe plan, no matter how many times it's asked.

Behavioral + live, so marked `llm` (runs under `task eval:llm` / nightly).
"""
import json
import pathlib

import pytest

DATASET = pathlib.Path(__file__).parent / "datasets" / "safety_insistence.jsonl"
CASES = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]
IDS = [c["id"] for c in CASES]


def _run_conversation(agent, case):
    """Drive all turns on one thread and return the final response."""
    response = ""
    thread_id = f"insist-{case['id']}"
    for turn in case["turns"]:
        for ev in agent.stream(turn, thread_id):
            if ev["type"] == "final":
                response = ev["content"]
    return response


@pytest.mark.llm
@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_holds_safety_line_under_insistence(case, agent, safety_judge):
    """After the teacher insists, the agent must not output an unsafe plan."""
    final = _run_conversation(agent, case)
    verdict = safety_judge.judge(final, case["turns"][-1])
    assert not verdict.unsafe_activity, (
        f"agent produced an unsafe plan after insistence "
        f"[{case['hazard']}]; judge flagged: {verdict.unsafe_items}"
    )
