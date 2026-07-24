# syntax=docker/dockerfile:1
# Violet assistant-core (FastAPI). Build context = repo root.
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    LLM_PROVIDER=mock \
    DATABASE_URL=sqlite:////app/data/violet.db

WORKDIR /app

# The package resolves repo_root as parents[4] of config.py, so it must stay at
# /app/services/assistant-core/src/... — an editable install keeps it in place
# while still pulling runtime deps (fastapi, uvicorn, pydantic).
COPY pyproject.toml ./
COPY services/ ./services/
COPY database/ ./database/
COPY configs/ ./configs/

RUN pip install --no-cache-dir -e . \
    && mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "violet_assistant.main:app", "--host", "0.0.0.0", "--port", "8000"]
