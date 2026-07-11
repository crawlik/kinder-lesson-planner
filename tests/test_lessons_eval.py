"""Evaluation unit tests, driven by a dataset curated from real Tempo traces.

Two tiers:
  * Deterministic (no marker): replay recorded agent outputs and assert on
    structure and tool-use. Fast, offline, safe for every CI run.
  * LLM-as-a-judge (@pytest.mark.llm): score the plan with two independent
    judges — the domain rubric (LessonReviewer) and an independent SafetyJudge —
    plus optional OpenLIT platform evals. Needs API keys.

Run:
    uv run pytest -m "not llm"     # deterministic gate
    uv run pytest -m llm           # judged evals
    uv run pytest                  # everything
"""
import pytest

import _helpers as H
from src.evals import run_openlit_eval

CASES = H.load_cases()
IDS = [c["id"] for c in CASES]

# Every test in this module is parametrized over the curated cases.
pytestmark = pytest.mark.parametrize("case", CASES, ids=IDS)


def _recorded(case):
    run = H.recorded_run(case["id"])
    if run is None:
        pytest.skip(f"no recording for {case['id']}; run scripts/record_runs.py")
    return run


# --------------------------- deterministic gate ---------------------------

def test_plan_nonempty(case):
    assert _recorded(case)["plan"].strip(), "agent produced an empty plan"


def test_required_sections_present(case):
    plan = _recorded(case)["plan"]
    missing = H.has_sections(plan, case["asserts"]["required_sections"])
    assert not missing, f"plan missing required sections: {missing}"


def test_web_search_behavior(case):
    run = _recorded(case)
    if case["asserts"]["must_call_web_search"]:
        assert "web_search" in run["tools_used"], (
            f"expected a web_search call; tools used: {run['tools_used']}"
        )


# --------------------------- LLM-as-a-judge gate ---------------------------

@pytest.mark.llm
def test_rubric_safety_and_age(case, reviewer):
    """Judge 1: the domain rubric (age-fit + safety must clear the floor)."""
    plan = _recorded(case)["plan"]
    review = reviewer.review(case["input"], plan)
    a = case["asserts"]
    assert review.scores.safety >= a["min_safety"], (
        f"safety {review.scores.safety} < required {a['min_safety']}; issues: {review.issues}"
    )
    assert review.scores.age_appropriateness >= a["min_age_appropriateness"], (
        f"age-fit {review.scores.age_appropriateness} < required {a['min_age_appropriateness']}"
    )


@pytest.mark.llm
def test_independent_safety_judge(case, safety_judge):
    """Judge 2: independent lens — no hallucinated resources, toxicity, or hazards."""
    plan = _recorded(case)["plan"]
    verdict = safety_judge.judge(plan, case["input"])
    assert verdict.passed, (
        f"safety judge flagged issues — hallucination={verdict.hallucination}, "
        f"toxicity={verdict.toxicity}, unsafe_activity={verdict.unsafe_activity}, "
        f"items={verdict.unsafe_items}"
    )


@pytest.mark.llm
def test_openlit_platform_eval_optional(case):
    """Judge 3 (optional): OpenLIT platform evals; skipped unless OPENLIT_API_KEY set."""
    plan = _recorded(case)["plan"]
    result = run_openlit_eval(case["input"], plan)
    if result is None:
        pytest.skip("OpenLIT platform evals not configured (set OPENLIT_API_KEY)")
    healthy = getattr(result, "healthy", None)
    assert result.success and (healthy is not False), (
        f"OpenLIT evals flagged: {getattr(result, 'unhealthy', result.evaluations)}"
    )
