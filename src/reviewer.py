"""LLM-as-a-judge review loop.

After the planner drafts a lesson, a second LLM is used as a judge playing the
role of a senior master teacher: it scores the draft against a rubric, flags
concrete issues (especially safety), and returns an improved version. This is a
small agentic reflection loop — generate, critique, refine — that raises quality
and catches problems (like choking hazards) the first pass may miss.
"""
import logging
import os
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

REVIEWER_SYSTEM_PROMPT = """You are a master kindergarten teacher and \
instructional coach with 20 years of classroom experience. A colleague has \
drafted a lesson plan for 4-6 year olds and asked for your review.

Score the draft on a 1-5 scale (5 = excellent) for each rubric dimension:
- age_appropriateness: developmentally right for ages 4-6 (attention span, \
motor skills, language, play-based).
- safety: free of choking hazards, sharp-tool risks, allergy concerns, and \
mobility issues — or clearly flags them. Be STRICT here.
- engagement: hands-on, playful, movement, and fun for young children.
- clarity: a substitute teacher could run it step by step.

Then:
- List concrete `issues`: anything unsafe, unclear, too advanced, or missing. \
Keep each item short and actionable. Empty list if genuinely none.
- Write a `revised_plan`: an IMPROVED version that fixes the issues while \
keeping the same 10-section Markdown structure and the teacher's original \
intent. Do not pad it — improve, don't bloat. If the draft is already strong, \
return it largely unchanged.
- Write a one-sentence `summary` of what you changed (or 'Already strong.').

Prioritize child safety and developmental fit above all else."""


class RubricScores(BaseModel):
    """1-5 scores across the review rubric."""

    age_appropriateness: int = Field(ge=1, le=5)
    safety: int = Field(ge=1, le=5)
    engagement: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)


class LessonReview(BaseModel):
    """Structured output of the master-teacher review."""

    scores: RubricScores
    issues: List[str] = Field(
        default_factory=list,
        description="Concrete, actionable problems or safety flags. Empty if none.",
    )
    summary: str = Field(description="One sentence on what was improved.")
    revised_plan: str = Field(
        description="The improved lesson plan as clean Markdown, same structure."
    )


class LessonReviewer:
    """Scores and refines a draft lesson plan using structured output."""

    def __init__(self, openai_api_key: str, model_name: str, temperature: float = 0.2):
        llm_kwargs = {"model": model_name, "openai_api_key": openai_api_key}
        # gpt-5*/o* models only accept the default temperature.
        if not model_name.startswith("gpt-5") and not model_name.startswith("o"):
            llm_kwargs["temperature"] = temperature
        self.llm = ChatOpenAI(**llm_kwargs).with_structured_output(LessonReview)

    def review(self, teacher_request: str, plan_text: str) -> LessonReview:
        """Review a draft plan and return scores + an improved version."""
        messages = [
            SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Teacher's request:\n{teacher_request}\n\n"
                    f"Draft lesson plan to review:\n{plan_text}"
                )
            ),
        ]
        return self.llm.invoke(messages)
