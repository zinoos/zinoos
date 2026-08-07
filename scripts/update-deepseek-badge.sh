#!/usr/bin/env bash
set -euo pipefail

JSON=$(npx tokscale@latest models --json 2>/dev/null)

if [ -z "$JSON" ]; then
  echo "Error: tokscale returned no data. Is it installed? Run: npx tokscale@latest"
  exit 1
fi

STATS=$(echo "$JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
entries = [e for e in data.get('entries',[]) if 'deepseek' in e.get('model','').lower()]
total_tokens = sum(
    e.get('input',0) + e.get('output',0) + e.get('cacheRead',0) +
    e.get('cacheWrite',0) + e.get('reasoning',0)
    for e in entries
)
total_cost = sum(e.get('cost',0) for e in entries)

def fmt_tokens(n):
    if n >= 1e9: return f'{n/1e9:.1f}B'
    if n >= 1e6: return f'{n/1e6:.1f}M'
    if n >= 1e3: return f'{n/1e3:.1f}K'
    return str(int(n))

def fmt_cost(n):
    if n >= 1e6: return f'\${n/1e6:.1f}M'
    if n >= 1e3: return f'\${n/1e3:.1f}K'
    return f'\${n:.2f}'

print(json.dumps({
    'tokens': total_tokens,
    'tokens_fmt': fmt_tokens(total_tokens),
    'cost': total_cost,
    'cost_fmt': fmt_cost(total_cost),
}))
")

if [ -z "$STATS" ]; then
  echo "Error: no DeepSeek stats found in tokscale data."
  exit 1
fi

TOKENS=$(echo "$STATS" | python3 -c "import json,sys; print(json.load(sys.stdin)['tokens_fmt'])")
COST=$(echo "$STATS" | python3 -c "import json,sys; print(json.load(sys.stdin)['cost_fmt'])")

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT="$REPO_DIR/deepseek-badge.json"

cat > "$OUTPUT" <<JSONEOF
{
  "schemaVersion": 1,
  "label": "DeepSeek",
  "message": "${TOKENS} tokens",
  "color": "4B32C2"
}
JSONEOF

echo "Updated $OUTPUT: DeepSeek → ${TOKENS} tokens (${COST})"
