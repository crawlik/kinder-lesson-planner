#!/usr/bin/env python3
"""Curate an evaluation dataset from real traces in Tempo.

Queries Tempo for `kinder-lesson-planner` traces, extracts the teacher request
and the observed behavior (did it search the web? what rubric scores did the
master-teacher give?), and emits one JSONL record per trace with regression-style
assertions plus the `source_trace_id` for full observability-to-eval lineage.

Usage:
    python scripts/export_traces.py > tests/datasets/lessons.jsonl
    python scripts/export_traces.py --tempo http://localhost:3200 --min-safety 3 --limit 20

Then review/trim the output — curation is a human step, exactly like picking
interesting traces in Grafana. This is the automated first pass.
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

REVIEWER_MARKER = "Draft lesson plan to review"


def _val(v):
    """Unwrap an OTLP attribute value ({'stringValue': ...} -> ...)."""
    return next(iter(v.values()))


def _get(attrs, key, default=None):
    return attrs.get(key, default)


def _fetch_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def search_trace_ids(tempo, limit, lookback_hours):
    q = '{ resource.service.name = "kinder-lesson-planner" }'
    now = int(time.time())
    params = {
        "q": q,
        "limit": limit,
        "start": now - int(lookback_hours * 3600),
        "end": now,
    }
    url = f"{tempo}/api/search?" + urllib.parse.urlencode(params)
    data = _fetch_json(url)
    return [t["traceID"] for t in data.get("traces", [])]


def extract_teacher_request(messages_json):
    """Return the first *user* message that isn't the reviewer's wrapper."""
    try:
        messages = json.loads(messages_json)
    except (json.JSONDecodeError, TypeError):
        return None
    for m in messages:
        if m.get("role") != "user":
            continue
        text = " ".join(
            p.get("content", "") for p in m.get("parts", []) if p.get("type") == "text"
        ).strip()
        if text and REVIEWER_MARKER not in text:
            return text
    return None


def summarize_trace(tempo, trace_id):
    d = _fetch_json(f"{tempo}/api/traces/{trace_id}")
    teacher_request = None
    called_web_search = False
    scores = {}
    for b in d.get("batches", []):
        for ss in b.get("scopeSpans", []):
            for sp in ss.get("spans", []):
                name = sp.get("name", "")
                attrs = {a["key"]: _val(a["value"]) for a in sp.get("attributes", [])}
                # Preferred: the short, untruncated custom attribute on lesson_turn.
                if "app.teacher_request" in attrs:
                    teacher_request = attrs["app.teacher_request"]
                if attrs.get("app.web_search_used") in (True, "true", "True"):
                    called_web_search = True
                if "web_search" in str(attrs.get("app.tools_used", "")):
                    called_web_search = True
                # Fallback: parse the (possibly truncated) captured messages.
                if teacher_request is None and name.startswith("chat"):
                    req = extract_teacher_request(attrs.get("gen_ai.input.messages", ""))
                    if req:
                        teacher_request = req
                if name.startswith("execute_tool") and (
                    attrs.get("gen_ai.tool.name") == "web_search"
                    or "web_search" in name
                ):
                    called_web_search = True
                if name == "evaluate_lesson":
                    for field in (
                        "safety",
                        "age_appropriateness",
                        "engagement",
                        "clarity",
                    ):
                        k = f"gen_ai.evaluation.{field}.score"
                        if k in attrs:
                            scores[field] = int(attrs[k])
    return teacher_request, called_web_search, scores


def slugify(text):
    import re

    s = re.sub(r"[^\w\s-]", "", (text or "").lower()).strip()
    return re.sub(r"[\s_-]+", "-", s)[:48].strip("-") or "case"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tempo", default="http://localhost:3200")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument(
        "--lookback-hours",
        type=float,
        default=6.0,
        help="How far back to search Tempo (default 6h).",
    )
    ap.add_argument(
        "--min-safety",
        type=int,
        default=3,
        help="Floor for the min_safety assertion (also clamped to observed-1).",
    )
    args = ap.parse_args()

    try:
        ids = search_trace_ids(args.tempo, args.limit, args.lookback_hours)
    except Exception as e:  # noqa: BLE001
        print(f"error: could not reach Tempo at {args.tempo}: {e}", file=sys.stderr)
        return 1

    emitted = 0
    seen_inputs = set()
    for tid in ids:
        try:
            request, web, scores = summarize_trace(args.tempo, tid)
        except Exception as e:  # noqa: BLE001
            print(f"warn: skipping {tid}: {e}", file=sys.stderr)
            continue
        if not request or request in seen_inputs:
            continue
        seen_inputs.add(request)

        # Regression-style asserts: keep at least the safety we already achieved
        # (floored at --min-safety), and keep searching if it searched.
        min_safety = args.min_safety
        if "safety" in scores:
            min_safety = max(args.min_safety, scores["safety"] - 1)

        record = {
            "id": slugify(request),
            "input": request,
            "asserts": {
                "must_call_web_search": bool(web),
                "required_sections": ["Objectives", "Materials", "Assessment"],
                "min_safety": min_safety,
                "min_age_appropriateness": 3,
            },
            "observed_scores": scores,
            "source_trace_id": tid,
        }
        print(json.dumps(record))
        emitted += 1

    print(f"exported {emitted} case(s) from {len(ids)} trace(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
