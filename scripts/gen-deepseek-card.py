#!/usr/bin/env python3
import json, sys, subprocess, os

def fmt_n(n):
    if n >= 1_000_000_000: return f"{n/1e9:.1f}B"
    if n >= 1_000_000: return f"{n/1e6:.1f}M"
    if n >= 1_000: return f"{n/1e3:.1f}K"
    return str(int(n))

def fmt_cost(n):
    if n >= 1e6: return f"${n/1e6:.1f}M"
    if n >= 1e3: return f"${n/1e3:.1f}K"
    return f"${n:.2f}"

def fmt_num(n):
    if n >= 1_000_000_000: return f"{n/1e9:.2f}B"
    if n >= 1_000_000: return f"{n/1e6:.2f}M"
    if n >= 1_000: return f"{n/1e3:.1f}K"
    return str(int(n))

def run_tokscale():
    result = subprocess.run(
        ["npx", "tokscale@latest", "models", "--json"],
        capture_output=True, text=True, timeout=30
    )
    return json.loads(result.stdout)

def get_deepseek_stats(data):
    entries = [e for e in data.get("entries", []) if "deepseek" in e.get("model", "").lower()]
    if not entries:
        raise SystemExit("No DeepSeek stats found")
    total_tokens = sum(e["input"] + e["output"] + e.get("cacheRead", 0) + e.get("cacheWrite", 0) + e.get("reasoning", 0) for e in entries)
    total_cost = sum(e["cost"] for e in entries)
    total_msgs = sum(e["messageCount"] for e in entries)

    models = []
    for e in entries:
        model_name = e["model"].replace("deepseek/", "").replace("deepseek-", "")
        client = e["client"]
        tokens = e["input"] + e["output"] + e.get("cacheRead", 0) + e.get("cacheWrite", 0) + e.get("reasoning", 0)
        models.append({
            "label": f"{client}/{model_name}",
            "tokens": tokens,
            "cost": e["cost"],
            "msgs": e["messageCount"],
        })

    models.sort(key=lambda x: x["tokens"], reverse=True)
    return {"tokens": total_tokens, "cost": total_cost, "messages": total_msgs, "models": models}

PALETTE = ["#4B32C2", "#6C5CE7", "#A29BFE", "#7C6FF7", "#5F4BD4", "#8B7CF6"]

def gen_svg(stats):
    N = len(stats["models"])
    W, H = 720, 200 + N * 26

    BAR_X = 300
    BAR_W = 390
    BAR_H = 16
    BAR_GAP = 10
    BAR_AREA_Y = 155

    max_tokens = stats["models"][0]["tokens"]
    total_all = stats["tokens"]
    COLORS = {"kilo": "#7C6FF7", "opencode": "#4B32C2", "kimi": "#A29BFE"}

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0d1117"/>
      <stop offset="100%" stop-color="#161b22"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#4B32C2"/>
      <stop offset="100%" stop-color="#8B7CF6"/>
    </linearGradient>
  </defs>

  <rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="url(#bg)"/>
  <rect x="0" y="0" width="{W}" height="{H}" rx="12" fill="none" stroke="#21262d" stroke-width="1"/>

  <text x="28" y="38" fill="#e6edf3" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="19" font-weight="700">DeepSeek Usage</text>
  <rect x="182" y="24" width="7" height="7" rx="3.5" fill="#6C5CE7"/>

  <text x="28" y="78" fill="#8b949e" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="10" font-weight="600" letter-spacing="1">TOKENS</text>
  <text x="28" y="106" fill="#e6edf3" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="28" font-weight="700">{fmt_n(stats["tokens"])}</text>
  <text x="28" y="120" fill="#8b949e" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="11">{fmt_num(stats["tokens"])} total</text>

  <text x="155" y="78" fill="#8b949e" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="10" font-weight="600" letter-spacing="1">COST</text>
  <text x="155" y="106" fill="#e6edf3" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="28" font-weight="700">{fmt_cost(stats["cost"])}</text>

  <text x="245" y="78" fill="#8b949e" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="10" font-weight="600" letter-spacing="1">MESSAGES</text>
  <text x="245" y="106" fill="#e6edf3" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="28" font-weight="700">{fmt_n(stats["messages"])}</text>

  <line x1="28" y1="138" x2="{W-28}" y2="138" stroke="#21262d" stroke-width="1"/>
'''

    for i, m in enumerate(stats["models"]):
        bar_w = max((m["tokens"] / max_tokens) * BAR_W, 3)
        y = BAR_AREA_Y + i * (BAR_H + BAR_GAP)
        client = m["label"].split("/")[0] if "/" in m["label"] else ""
        c = COLORS.get(client, PALETTE[i % len(PALETTE)])

        short = m["label"]
        if len(short) > 22:
            short = short[:21] + "…"

        pct_str = f" {m['tokens']/total_all*100:.0f}%" if m['tokens'] > 0 else ""

        svg += f'''
  <rect x="{BAR_X}" y="{y}" width="{bar_w:.1f}" height="{BAR_H}" rx="4" fill="{c}" opacity="0.9"/>
  <text x="{BAR_X + bar_w + 10:.0f}" y="{y + 12}" fill="#8b949e" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="10">{fmt_n(m["tokens"])}<tspan fill="#484f58">{pct_str}</tspan></text>
  <text x="{BAR_X - 10}" y="{y + 12}" fill="#c9d1d9" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="10" text-anchor="end">{short}</text>
'''

    svg += f'''
  <text x="28" y="{H - 14}" fill="#484f58" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="9">via Kilo + OpenCode + Kimi  ·  <tspan fill="#6C5CE7">tokscale</tspan></text>
</svg>'''
    return svg

def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "deepseek-card.svg"
    data = run_tokscale()
    stats = get_deepseek_stats(data)
    svg = gen_svg(stats)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"Generated {out_path}: {fmt_n(stats['tokens'])} tokens, {fmt_cost(stats['cost'])}, {fmt_n(stats['messages'])} msgs")

if __name__ == "__main__":
    main()
