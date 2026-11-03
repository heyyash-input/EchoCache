FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-cache

RUN useradd --create-home --uid 10001 echocache && mkdir -p /app/data/models && chown -R echocache:echocache /app/data
COPY app ./app
COPY static ./static
COPY policies.md ./policies.md

USER echocache
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
