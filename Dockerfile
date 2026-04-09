# ABOUTME: Docker image for Illinois Report Card API
# ABOUTME: Uses Python 3.12 slim with uv for dependency management

FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files and README
COPY pyproject.toml README.md ./

# Copy application code (needed for package installation)
COPY app/ app/

# Install dependencies (regular install, not editable)
RUN uv pip install --system .

# Copy data directory
COPY data/ data/

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
