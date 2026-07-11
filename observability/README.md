# Grafana AI Observability (local stack)

Traces and metrics for the agent, powered by [OpenLIT](https://openlit.io)
(OpenTelemetry-native) → OTel Collector → **Tempo** (traces) + **Prometheus**
(metrics) → **Grafana**.

```
app (OpenLIT SDK) ──OTLP:4318──▶ otel-collector ──▶ Tempo   (traces)
                                              └────▶ Prometheus (metrics)
                                                     Grafana visualizes both
```

## Run it

```bash
# 1. Start the stack
docker compose -f observability/docker-compose.yaml up -d

# 2. Point the app at it (already the default in .env.example)
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

# 3. Use the app — every turn is now traced
uv run python main.py
```

Open **http://localhost:3000** (anonymous admin, no login):
- **Dashboards → AI Observability → Kinder Lesson Planner — GenAI Observability**
- Or **Explore → Tempo**, run `{ resource.service.name = "kinder-lesson-planner" }`

## What you'll see

Each turn produces an OTel GenAI span tree:

- `invoke_agent` — the LangGraph turn
- `chat` — each LLM call (planner **and** the master-teacher reviewer)
- `execute_tool` — `web_search` (+ the Tavily HTTP span) and `save_lesson_plan`
- `evaluate_lesson` — our custom span carrying the rubric scores as attributes:
  `gen_ai.evaluation.safety.score`, `age_appropriateness.score`,
  `engagement.score`, `clarity.score`, plus `issue_count` / `revised`

Token counts, estimated cost, and latency are captured automatically and charted
via TraceQL metrics + the OpenLIT Prometheus metrics.

## Grafana Cloud instead

Skip the stack and set the OTLP gateway + credentials in `.env` (see
`.env.example`). Grafana Cloud's AI Observability app ships the five prebuilt
dashboards (GenAI observability, GenAI evaluations, Vector DB, MCP, GPU).

## Notes

- Storage is ephemeral (no volumes) — restart wipes traces. Fine for a demo.
- Some Prometheus panels depend on exact OpenLIT metric names and may show
  "No data" until the first traced run; the Tempo panels populate immediately.
