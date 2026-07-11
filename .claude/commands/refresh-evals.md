---
description: Rebuild the eval dataset from Tempo traces and run the full suite
---

Refresh and verify the evaluation suite end-to-end:

1. Ensure the observability stack is running (`task obs:up`); start it if not, and
   confirm Tempo is reachable at http://localhost:3200/ready.
2. Make sure there are recent traces to curate from — if Tempo is empty, run a few
   representative turns through the app first (include at least one safety edge case).
3. Run `task dataset` to export cases from Tempo (`scripts/export_traces.py`) and
   re-record agent outputs (`scripts/record_runs.py`).
4. Run `task eval` (deterministic), then `task eval:llm` (both judges).
5. Summarize pass/fail counts and any rubric-safety regressions. If a case regressed,
   show the reviewer's flagged issues and the `source_trace_id` so it can be inspected
   in Grafana.
