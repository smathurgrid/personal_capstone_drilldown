#!/usr/bin/env bash
# Mac 2 — run the dedicated Flux image worker (distributed inference).
# Requires Ollama running locally on Mac 2 with the Flux model pulled:
#   ollama pull x/flux2-klein:4b-bf16
# Usage:  ./scripts/run_flux_worker.sh
#         IMAGE_MODEL=x/flux2-klein:4b-bf16 OLLAMA_BASE=http://localhost:11434 ./scripts/run_flux_worker.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# The venv lives in the main checkout, not the git worktree.
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
elif [ -f ../../../venv/bin/activate ]; then
  source ../../../venv/bin/activate
else
  echo "ERROR: could not find venv (looked in ./venv and ../../../venv)" >&2
  exit 1
fi
export PYTHONPATH=.
export OLLAMA_BASE="${OLLAMA_BASE:-http://localhost:11434}"
export IMAGE_MODEL="${IMAGE_MODEL:-x/flux2-klein:4b-bf16}"
echo "Flux worker -> http://0.0.0.0:9000   model=$IMAGE_MODEL   ollama=$OLLAMA_BASE"
exec python -m uvicorn backend.worker.flux_server:app --host 0.0.0.0 --port 9000
