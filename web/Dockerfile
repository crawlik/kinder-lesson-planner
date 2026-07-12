# Web backend (FastAPI + SSE) for the lesson-planner agent.
# Build from the REPO ROOT:
#   docker build -f web/Dockerfile -t kinder-lesson-planner-web .
# Run (keys via .env; tracing off unless you point OTEL at the host):
#   docker run --rm -p 8000:8000 --env-file .env -e TRACING_ENABLED=false kinder-lesson-planner-web
FROM python:3.10-slim-bookworm

# uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# 1) Dependencies only (cached until pyproject/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra web

# 2) App source, then install the project itself
COPY src ./src
COPY web ./web
RUN uv sync --frozen --no-dev --extra web

ENV PATH="/app/.venv/bin:$PATH"
# Tracing off by default in-container; to enable, pass
#   -e TRACING_ENABLED=true -e OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318
ENV TRACING_ENABLED=false
EXPOSE 8000
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
