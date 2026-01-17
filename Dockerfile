# ABOUTME: Docker image for Illinois Report Card API
# ABOUTME: Uses Python 3.12 slim with uv for dependency management

FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .
RUN uv pip install --system -e .

# Copy application code
COPY app/ app/
COPY data/ data/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
