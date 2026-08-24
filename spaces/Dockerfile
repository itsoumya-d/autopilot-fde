# Hugging Face Space: public hosted AutoPilot FDE MCP server (Docker SDK).
# Deploy with docs/DEPLOY-HF-SPACE.md — the Space serves the dashboard API
# AND the Streamable-HTTP MCP endpoint at /mcp, earning the Hub's MCP badge.

FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/

# Spaces expects the app on $PORT (7860 by default); a writable workspace
# volume lives at /data for the SQLite store.
ENV AUTOPILOT_DB_PATH=/data/autopilot.db \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
