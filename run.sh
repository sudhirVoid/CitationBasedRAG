#!/usr/bin/env bash
# Start the citation-RAG app: one FastAPI process serves both the API (BE)
# and the static chat/PDF-viewer frontend (FE) together on one port.

set -e

PORT=8000
HOST=127.0.0.1

cd "$(dirname "$0")"

# Stop any process already bound to $PORT (best-effort; won't abort startup
# if this fails). Uses a .ps1 file instead of an inline command to avoid
# Git Bash quoting issues with multi-line PowerShell strings.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/kill_port.ps1 -Port "$PORT" || true

echo "Starting server at http://$HOST:$PORT"
.venv/Scripts/python.exe -m uvicorn server:app --app-dir src/citation_rag --host "$HOST" --port "$PORT"
