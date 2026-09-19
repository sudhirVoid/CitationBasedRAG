#!/usr/bin/env bash
# Debug mode: starts the server under debugpy so VS Code can attach and hit
# breakpoints on incoming requests. No --reload here — a reload subprocess
# would break the debugger's attach to the actual running process.

set -e

PORT=8000
HOST=127.0.0.1
DEBUG_PORT=5678

cd "$(dirname "$0")"

# Stop any process already bound to $PORT (best-effort; won't abort startup
# if this fails). Uses a .ps1 file instead of an inline command to avoid
# Git Bash quoting issues with multi-line PowerShell strings.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/kill_port.ps1 -Port "$PORT" || true

echo "Starting server (DEBUG mode) at http://$HOST:$PORT"
echo "Waiting for a debugger to attach on port $DEBUG_PORT..."
echo "In VS Code: Run and Debug -> 'Python: Attach to Debug Server'"

.venv/Scripts/python.exe -m debugpy --listen "$DEBUG_PORT" --wait-for-client -m uvicorn \
  server:app \
  --app-dir src/citation_rag \
  --host "$HOST" \
  --port "$PORT" \
  --log-level debug
