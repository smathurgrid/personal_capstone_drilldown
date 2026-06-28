#!/usr/bin/env bash
# Launch the backend for the speculative drill demo.
#   MODEL_PROVIDER=mock  -> instant placeholder images (fast; real VLM ranking)
#   MODEL_PROVIDER=ollama -> real Flux image generation (slow)
# Usage:  ./scripts/run_spec_backend.sh           # mock images (default)
#         MODEL_PROVIDER=ollama ./scripts/run_spec_backend.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# The venv lives in the main checkout, not the git worktree. Try local first,
# then the main repo root (worktrees sit at .claude/worktrees/<name>).
if [ -f venv/bin/activate ]; then
  VENV="venv/bin/activate"
elif [ -f ../../../venv/bin/activate ]; then
  VENV="../../../venv/bin/activate"
else
  echo "ERROR: could not find venv (looked in ./venv and ../../../venv)" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$VENV"
export MODEL_PROVIDER="${MODEL_PROVIDER:-mock}"
export LLM_PROVIDER="${LLM_PROVIDER:-ollama}"
export PYTHONPATH=.
echo "MODEL_PROVIDER=$MODEL_PROVIDER  LLM_PROVIDER=$LLM_PROVIDER  ->  http://127.0.0.1:8000"
exec python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
