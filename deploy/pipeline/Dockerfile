FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

RUN uv add dbt-bigquery

COPY src/ ./src/
COPY run_scrape.py .
COPY run_pipeline.py .
COPY dbt/edikte_dbt ./dbt/edikte_dbt

ENV PYTHONPATH=/app/src