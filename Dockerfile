FROM python:3.12-slim

# Minimal system deps for Phase 1a (psycopg2 needs libpq)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY data/ ./data/
COPY scripts/ ./scripts/

EXPOSE 8000

CMD ["uvicorn", "src.lms_agents.main:app", "--host", "0.0.0.0", "--port", "8000"]
