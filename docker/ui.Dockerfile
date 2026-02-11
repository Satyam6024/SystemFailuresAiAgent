FROM python:3.13-slim

WORKDIR /app

# System deps for pycairo (xhtml2pdf dependency)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc pkg-config libcairo2-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Install dependencies
RUN uv sync --frozen --no-dev

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit
CMD ["uv", "run", "streamlit", "run", "src/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]