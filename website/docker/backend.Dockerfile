FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files (context is website directory)
COPY backend/pyproject.toml .
COPY backend/config.py .
COPY backend/main.py .

# Install dependencies
RUN uv sync --no-dev

# Expose port
EXPOSE 37801

# Run the application (no hot reload in production)
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "37801"]
