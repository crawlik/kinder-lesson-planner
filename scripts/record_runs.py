#!/usr/bin/env python3
"""Record agent outputs for each dataset case into tests/fixtures/runs/.

The deterministic test suite replays these recordings so it runs offline and
fast (no LLM calls). Re-run this whenever the dataset or the agent changes.

    python scripts/record_runs.py
"""
import json
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests"))

from tests._helpers import RUNS_DIR, load_cases, run_turn  # noqa: E402


def main() -> int:
    load_dotenv()
    if not (os.getenv("OPENAI_API_KEY") and os.getenv("TAVILY_API_KEY")):
        print("error: OPENAI_API_KEY and TAVILY_API_KEY required to record.", file=sys.stderr)
        return 1

    from src.agent import create_agent  # noqa: E402

    agent = create_agent(os.environ["OPENAI_API_KEY"], os.environ["TAVILY_API_KEY"])
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    cases = load_cases()
    for i, case in enumerate(cases):
        result = run_turn(agent, case["input"], f"record-{i}")
        record = {"id": case["id"], "input": case["input"], **result}
        (RUNS_DIR / f"{case['id']}.json").write_text(json.dumps(record, indent=2))
        s = (result["review_scores"] or {}).get("safety", "-")
        print(f"recorded {case['id']}  tools={result['tools_used']} safety={s}")

    print(f"wrote {len(cases)} recording(s) to {RUNS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
