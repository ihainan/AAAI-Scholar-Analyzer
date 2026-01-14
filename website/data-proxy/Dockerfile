FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY config.py .
COPY main.py .
COPY utils/ ./utils/
COPY services/ ./services/
COPY routes/ ./routes/

# Install dependencies
RUN uv sync --no-dev

# Note: Port is configured via environment variables (PORT in .env.prod)
# Docker Compose will handle port mapping via ports: "${HOST_PORT}:${PORT}"

# Run the application via main.py which reads config from settings
CMD ["uv", "run", "python", "main.py"]
