FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files (context is website directory)
COPY data-proxy/pyproject.toml .
COPY data-proxy/config.py .
COPY data-proxy/main.py .
COPY data-proxy/utils/ ./utils/
COPY data-proxy/services/ ./services/
COPY data-proxy/routes/ ./routes/

# Install dependencies
RUN uv sync --no-dev

# Expose port
EXPOSE 37803

# Run the application (no hot reload in production)
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "37803"]
