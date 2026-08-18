FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY src/ ./src/
COPY streamlit_app.py .
COPY pages/ ./pages/
ENV PYTHONPATH=/app/src
EXPOSE 8080
CMD ["uv", "run", "streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]