FROM ghcr.io/astral-sh/uv:0.13.5 AS uv
FROM python:3.13-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY config ./config
RUN uv sync --locked --no-dev

FROM python:3.13-slim
RUN useradd --uid 10001 --create-home app && mkdir -p /app/data && chown app /app/data
WORKDIR /app
COPY --from=build /app /app
ENV PATH=/app/.venv/bin:$PATH RCC_ROOT=/app RCC_PROVIDER=mock RCC_DOTENV=off \
    RCC_DB_URL=sqlite:////app/data/rcc.db
USER app
VOLUME ["/app/data"]
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2).status==200 else 1)"
CMD ["uvicorn", "--factory", "robot_copilot.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
