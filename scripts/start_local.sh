#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q -r requirements.txt
if [[ ! -f .env ]]; then cp .env.example .env; fi
mkdir -p data
uvicorn lab.main:app --host 127.0.0.1 --port 8001 & LAB_PID=$!
trap 'kill "$LAB_PID" 2>/dev/null || true' EXIT
uvicorn app.main:app --host 127.0.0.1 --port 8501
