#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
python3 "$SCRIPT_DIR/gen-deepseek-card.py" "$REPO_DIR/deepseek-card.svg"
echo "Done. Commit and push:"
echo "  git add deepseek-card.svg && git commit -m 'update deepseek stats' && git push"
