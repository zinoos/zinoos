#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

python3 "$SCRIPT_DIR/gen-deepseek-card.py" "$REPO_DIR/deepseek-card.svg"

JSON_DATA=$(npx tokscale@latest models --json 2>/dev/null)
if [ -n "$JSON_DATA" ]; then
  STATS=$(echo "$JSON_DATA" | python3 -c "
import json, sys
data = json.load(sys.stdin)
entries = [e for e in data.get('entries',[]) if 'deepseek' in e.get('model','').lower()]
total_tokens = sum(e.get('input',0)+e.get('output',0)+e.get('cacheRead',0)+e.get('cacheWrite',0)+e.get('reasoning',0) for e in entries)
def fmt(n):
    if n >= 1e9: return f'{n/1e9:.1f}B'
    if n >= 1e6: return f'{n/1e6:.1f}M'
    if n >= 1e3: return f'{n/1e3:.1f}K'
    return str(int(n))
print(json.dumps({'schemaVersion':1,'label':'DeepSeek','message':f'{fmt(total_tokens)} tokens','color':'4B32C2'}))
")
  echo "$JSON_DATA" > "$REPO_DIR/deepseek-badge.json"
fi

echo "Update complete. Commit and push to refresh:"
echo "  git add deepseek-card.svg deepseek-badge.json && git commit -m 'update deepseek stats' && git push"
