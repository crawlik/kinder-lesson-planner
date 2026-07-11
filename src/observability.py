"""Grafana AI Observability wiring via OpenLIT (OpenTelemetry-native).

`init_tracing()` turns on OpenLIT, which auto-instruments LangChain/LangGraph,
OpenAI, and outbound HTTP (Tavily) and exports OTel GenAI spans + metrics over
OTLP. Point it at the local Docker stack (Tempo + Prometheus + Grafana) or at
Grafana Cloud via the standard OTEL_* environment variables.

It's fully optional: if tracing isn't enabled the app runs unchanged, and the
score-recording helpers degrade to cheap no-ops (OpenTelemetry returns a
non-recording span when no provider is configured).
"""
import logging
import os
from typing import Optional

from opentelemetry import trace

logger = logging.getLogger(__name__)

_INITIALIZED = False


def tracing_enabled() -> bool:
    """Enabled when explicitly turned on, or when an OTLP endpoint is set."""
    if os.getenv("TRACING_ENABLED", "").lower() == "true":
        return True
    if os.getenv("TRACING_ENABLED", "").lower() == "false":
        return False
    return bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))


def init_tracing(force: bool = False) -> bool:
    """Initialize OpenLIT tracing. Returns True if tracing was turned on.

    Safe to call more than once. OpenLIT reuses an already-configured global
    TracerProvider, or builds its own OTLP exporter from OTEL_EXPORTER_OTLP_*.
    Pass `force=True` to init even when no OTLP endpoint is set (e.g. tests that
    have installed their own in-memory provider).
    """
    global _INITIALIZED
    if _INITIALIZED:
        return True
    if not force and not tracing_enabled():
        return False

    try:
        import openlit

        openlit.init(
            application_name=os.getenv("OTEL_SERVICE_NAME", "kinder-lesson-planner"),
            environment=os.getenv("OTEL_DEPLOYMENT_ENVIRONMENT", "dev"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            disable_metrics=False,
        )
        _INITIALIZED = True
        logger.info("OpenLIT tracing initialized")
        return True
    except Exception as e:  # noqa: BLE001 - observability must never break the app
        logger.warning("Could not initialize tracing (continuing without it): %s", e)
        return False


def get_tracer():
    """Return a tracer. No-ops cheaply if no provider is configured."""
    return trace.get_tracer("kinder-lesson-planner")


# Map rubric fields -> OTel-style evaluation attribute names.
_EVAL_ATTRS = {
    "age_appropriateness": "gen_ai.evaluation.age_appropriateness.score",
    "safety": "gen_ai.evaluation.safety.score",
    "engagement": "gen_ai.evaluation.engagement.score",
    "clarity": "gen_ai.evaluation.clarity.score",
}


def record_review_scores(
    span, scores: dict, issue_count: int = 0, revised: bool = False
) -> None:
    """Attach master-teacher rubric scores to a span as queryable attributes."""
    if span is None or not getattr(span, "is_recording", lambda: False)():
        return
    for field, attr in _EVAL_ATTRS.items():
        if field in scores and scores[field] is not None:
            span.set_attribute(attr, int(scores[field]))
    span.set_attribute("gen_ai.evaluation.issue_count", int(issue_count))
    span.set_attribute("gen_ai.evaluation.revised", bool(revised))
