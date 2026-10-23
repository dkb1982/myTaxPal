# syntax=docker/dockerfile:1.7
# myTaxPal API + static frontend. Stateless: no database, rules are bundled.
#
#   docker build -t mytaxpal .
#   docker run --rm -p 8000:8000 mytaxpal
#
# The app locates rules/ and static/ relative to the source tree, so the
# project is installed in editable mode from /app rather than as a wheel.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first for layer caching
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY rules ./rules
COPY static ./static
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 app && chown -R app /app
USER app

ENV PATH="/app/.venv/bin:$PATH" \
    TAX_ESTIMATOR_HOST=0.0.0.0 \
    TAX_ESTIMATOR_PORT=8000 \
    TAX_ESTIMATOR_DEBUG=false

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

# --proxy-headers lets uvicorn honour X-Forwarded-Proto behind a platform TLS proxy.
CMD ["uvicorn", "tax_estimator.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
