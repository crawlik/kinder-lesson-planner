"""Pytest fixtures for the evaluation suite."""
import os

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="session")
def keys_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") and os.getenv("TAVILY_API_KEY"))


@pytest.fixture(scope="session")
def reviewer(keys_available):
    """The domain rubric judge (reused from the runtime review loop)."""
    if not keys_available:
        pytest.skip("OPENAI_API_KEY/TAVILY_API_KEY not set")
    from src.agent import resolve_model
    from src.reviewer import LessonReviewer

    return LessonReviewer(os.environ["OPENAI_API_KEY"], resolve_model())


@pytest.fixture(scope="session")
def safety_judge(keys_available):
    """The independent safety/groundedness judge."""
    if not keys_available:
        pytest.skip("OPENAI_API_KEY/TAVILY_API_KEY not set")
    from src.evals import SafetyJudge

    return SafetyJudge(os.environ["OPENAI_API_KEY"])
