"""FastAPI + SSE backend wrapping the lesson-planner agent.

Streams the agent's events (tool_call / reviewing / review / final) to the
browser as Server-Sent Events, reusing `agent.stream()` unchanged. This is the
enabler for any web UI (a Lovable front end, HTMX, React, …) without touching
the terminal app.

Run locally (bypasses `uv run` so it won't re-sync the venv):
    .venv/bin/python -m uvicorn web.app:app --reload --port 8000
Then open http://localhost:8000
"""
import json
import os
import pathlib
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

load_dotenv()

from src.agent import create_agent, resolve_model  # noqa: E402
from src.observability import init_tracing  # noqa: E402

REQUIRED_VARS = ["OPENAI_API_KEY", "TAVILY_API_KEY"]
STATIC = pathlib.Path(__file__).parent / "static"

_agent = None


def get_agent():
    """Create the agent once (lazily, so startup stays fast)."""
    global _agent
    if _agent is None:
        missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
        if missing:
            raise RuntimeError(f"Missing env vars: {', '.join(missing)}")
        _agent = create_agent(os.environ["OPENAI_API_KEY"], os.environ["TAVILY_API_KEY"])
    return _agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tracing()  # honors .env; no-op if tracing isn't configured
    yield


app = FastAPI(title="Kinder Lesson Planner API", lifespan=lifespan)

# Allow a separately-hosted front end (e.g. Lovable) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable proxy buffering so events flush live
}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _event_stream(message: str, thread_id: str):
    """Sync generator — Starlette runs it in a threadpool, so the blocking
    LLM calls don't stall the event loop."""
    try:
        for event in get_agent().stream(message, thread_id):
            yield _sse(event)
    except Exception as e:  # noqa: BLE001
        yield _sse({"type": "error", "error": str(e)})
    yield _sse({"type": "done"})


@app.get("/health")
def health():
    return {"status": "ok", "model": resolve_model()}


@app.post("/chat")
async def chat_post(req: Request):
    """Canonical endpoint: POST {message, thread_id} -> SSE stream."""
    body = await req.json()
    message = (body.get("message") or "").strip()
    thread_id = body.get("thread_id") or "web"
    if not message:
        return JSONResponse({"error": "message is required"}, status_code=400)
    return StreamingResponse(
        _event_stream(message, thread_id),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@app.get("/chat")
def chat_get(message: str, thread_id: str = "web"):
    """Convenience GET for curl / EventSource testing."""
    return StreamingResponse(
        _event_stream(message, thread_id),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@app.get("/")
def index():
    return HTMLResponse((STATIC / "index.html").read_text())
