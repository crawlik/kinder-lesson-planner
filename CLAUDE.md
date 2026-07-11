# CLAUDE.md

Guidance for Claude Code (and humans) working in this repo. Keep it short and current.

## What this is
An agentic **kindergarten lesson-plan generator**: a LangGraph ReAct agent (OpenAI)
with a web-search tool and an **LLM-as-a-judge review loop**, shown as a colorful
Rich terminal app. Instrumented with **OpenLIT → Grafana** (Tempo/Prometheus) and
checked by a **trace-seeded pytest** suite.

## Commands (source of truth: `Taskfile.yml` — run `task --list`)
- `task run` — launch the app (needs `.env`)
- `task eval` — deterministic gate (offline, fast); **run before committing**
- `task eval:llm` — LLM-judge gate (needs API keys)
- `task obs:up` / `task obs:down` — local Grafana stack (Docker)
- `task dataset` — rebuild the eval dataset from Tempo traces

Toolchain: [`uv`](https://docs.astral.sh/uv/), [`go-task`](https://taskfile.dev),
and Docker (for observability only).

## Layout
- `src/agent.py` — LangGraph ReAct agent; `stream()` yields events; wraps each turn in a `lesson_turn` span
- `src/reviewer.py` — master-teacher rubric judge (the runtime review loop)
- `src/evals.py` — independent `SafetyJudge` + optional OpenLIT platform eval
- `src/observability.py` — OpenLIT/OTel init (guarded, optional) + score-recording helper
- `src/cli.py` — Rich terminal REPL; `src/tools/` — `web_search` (Tavily), `save_lesson_plan`
- `observability/` — docker-compose stack + Grafana provisioning
- `scripts/` — `export_traces.py` (Tempo→dataset), `record_runs.py` (offline fixtures)
- `tests/` — `datasets/lessons.jsonl`, recorded `fixtures/`, the pytest suite

## Conventions
- Config via `.env` (copy `.env.example`); **never commit it**.
- The model is read from `OPENAI_MODEL` at runtime — don't hardcode it.
- Add deps with `uv add`; dev deps live under `[dependency-groups] dev`.
- Commits are attributed to the repo owner's GitHub noreply email.

## Gotchas (learned the hard way)
- **Model/temperature:** `gpt-5*`/`o*` models reject a custom temperature — the code
  omits it for those. This OpenAI project only has access to `gpt-5.4`.
- **Tracing is optional:** a no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` (or
  `TRACING_ENABLED=true`) is set, and it must init *before* the agent so the
  LLM/HTTP libraries get instrumented.
- **Tempo truncates long span attributes:** the full prompt isn't recoverable from
  `gen_ai.input.messages`, so each turn records a short `app.teacher_request` on the
  `lesson_turn` span — that's what `export_traces.py` reads.
- **Eval tiers:** deterministic tests replay `tests/fixtures/runs/*.json` (offline,
  no LLM). Regenerate with `task dataset` after changing the agent or dataset.
- **`task` is go-task**, not Taskwarrior (same binary name).

## When you change things
- Changed the agent or prompts → `task dataset` (re-export + re-record) then `task eval`.
- Adding an eval case → append to `tests/datasets/lessons.jsonl` (include a
  `source_trace_id`) and run `task dataset:record`.
- Always run `task eval` before committing; it's the fast offline gate.
