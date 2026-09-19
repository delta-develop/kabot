FROM python:3.11.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /bin/uv

ARG SERVICE
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /src

COPY pyproject.toml uv.lock ./
COPY services/core-api/pyproject.toml services/core-api/
COPY services/agent/pyproject.toml services/agent/
COPY services/memory/pyproject.toml services/memory/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package "$SERVICE"

COPY services/$SERVICE services/$SERVICE

WORKDIR /src/services/$SERVICE

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
