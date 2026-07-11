"""Shared helpers for the evaluation tests."""
import json
import pathlib

TESTS_DIR = pathlib.Path(__file__).parent
DATASET = TESTS_DIR / "datasets" / "lessons.jsonl"
RUNS_DIR = TESTS_DIR / "fixtures" / "runs"


def load_cases():
    """Load the curated evaluation dataset (one case per line)."""
    if not DATASET.exists():
        return []
    return [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]


def recorded_run(case_id: str):
    """Return the recorded agent output for a case, or None if not recorded."""
    path = RUNS_DIR / f"{case_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def run_turn(agent, text: str, thread_id: str) -> dict:
    """Drive one agent turn and collect plan, tools used, and review scores."""
    plan, tools, scores = "", [], None
    for ev in agent.stream(text, thread_id):
        if ev["type"] == "tool_call":
            tools.append(ev["name"])
        elif ev["type"] == "review":
            scores = ev["scores"]
        elif ev["type"] == "final":
            plan = ev["content"]
    return {"plan": plan, "tools_used": tools, "review_scores": scores}


def has_sections(plan: str, sections) -> list:
    """Return the list of required sections missing from the plan (case-insensitive)."""
    low = plan.lower()
    return [s for s in sections if s.lower() not in low]
