FROM python:3.13-slim

WORKDIR /app

# System deps for async DB drivers + pycairo (xhtml2pdf dependency)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev pkg-config libcairo2-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY alembic.ini ./
COPY migrations/ migrations/

# Install dependencies (no dev deps in production)
RUN uv sync --frozen --no-dev

# Expose API port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uv", "run", "uvicorn", "src.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]