#!/usr/bin/env python3
"""Render the profile README's ASCII space scenes as animated SVGs.

Stdlib only. Live data comes from the GitHub GraphQL API (GITHUB_TOKEN);
without a token it falls back to sample data so the art can be previewed.

    GITHUB_TOKEN=$(gh auth token) python3 scripts/build.py
"""

import base64, datetime as dt, json, math, os, random, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
FONTS = Path(__file__).resolve().parent / "fonts"

LOGIN = "zinoos"
NAME = "zino"
BASE = ("zürich, earth", "47.37°N 8.54°E")
CREW = "developer @ accenture"
VESSEL = "fedora · hyprland · zed"
FEATURED = ["agent-control", "hypr-computer"]
SKIP_LANGS = {"TeX"}
TAGLINES = [
    "hi, i'm zino · developer from zürich",
    "giving ai agents their own desktops",
    "currently orbiting: hyprland · agents · games",
]

# palette
BG0, BG1 = "#05060c", "#0b1022"
INK, DIM, FAINT = "#e6e9f5", "#7d87a8", "#3a4363"
GOLD, PINK, VIOLET, CYAN = "#fde68a", "#f472b6", "#a78bfa", "#67e8f9"

W = 840


# ── svg plumbing ────────────────────────────────────────────────────────────

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def font_css(*weights):
    css = []
    for w in weights:
        b64 = base64.b64encode((FONTS / f"jbm-{w}.woff2").read_bytes()).decode()
        num = 700 if w == "bold" else 400
        css.append(f"@font-face{{font-family:'JBM';font-weight:{num};"
                   f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "".join(css)


def doc(h, body, css="", defs="", weights=("regular",)):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}">'
            f"<style>{font_css(*weights)}"
            "text{font-family:'JBM',ui-monospace,'SFMono-Regular',Menlo,Consolas,monospace;white-space:pre}"
            f"{css}</style><defs>{defs}</defs>{body}</svg>")


class Palette:
    """Maps fill colours to short CSS classes so dense ASCII art stays small."""

    def __init__(self, prefix):
        self.prefix, self.map = prefix, {}

    def __call__(self, color):
        if color not in self.map:
            self.map[color] = f"{self.prefix}{len(self.map)}"
        return self.map[color]

    def css(self):
        return "".join(f".{k}{{fill:{c}}}" for c, k in self.map.items())


def art_rows(grid, x0, y0, cw, lh, size, attrs=""):
    """grid: rows of (char, class|None). Emits one <text> per row, runs merged."""
    out = []
    for j, row in enumerate(grid):
        lead = 0
        while lead < len(row) and row[lead][0] == " ":
            lead += 1
        if lead == len(row):
            continue
        end = len(row)
        while row[end - 1][0] == " ":
            end -= 1
        parts, run, cls = [], "", None
        for ch, k in row[lead:end] + [("\0", "\0")]:
            k = None if ch == " " else k
            if run and (k != cls or ch == "\0"):
                parts.append(f'<tspan class="{cls}">{esc(run)}</tspan>' if cls else esc(run))
                run = ""
            run, cls = run + ch, k
        out.append(f'<text x="{x0 + lead * cw:.1f}" y="{y0 + j * lh:.1f}" font-size="{size}"{attrs}>{"".join(parts)}</text>')
    return "".join(out)


def frame(h, inner, rx=14):
    """Rounded deep-space panel every scene sits in."""
    return (f'<rect width="{W}" height="{h}" rx="{rx}" fill="url(#bg)"/>{inner}'
            f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="{rx}" fill="none" stroke="#1d2440"/>')


BG_DEF = (f'<radialGradient id="bg" cx="65%" cy="40%" r="90%">'
          f'<stop offset="0" stop-color="{BG1}"/><stop offset="1" stop-color="{BG0}"/></radialGradient>')
# soft nebula clouds as gradients: blur filters are far too slow once anything animates
HAZE = "".join(f'<radialGradient id="cloud{k}"><stop offset="0" stop-color="{c}" stop-opacity="1"/>'
               f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>'
               for k, c in enumerate(["#6d28d9", "#0e7490", "#be185d"]))


# ── math helpers ────────────────────────────────────────────────────────────

def norm(v):
    l = math.sqrt(sum(c * c for c in v))
    return tuple(c / l for c in v)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def scale(c, f):
    return mix("#000000", c, max(0.0, min(1.0, f)))


class Noise:
    def __init__(self, seed):
        r = random.Random(seed)
        self.v = [r.random() for _ in range(256)]
        self.perm = list(range(256))
        r.shuffle(self.perm)

    def _h(self, i, j):
        return self.v[(self.perm[i & 255] + j) & 255]

    def __call__(self, x, y):
        i, j = math.floor(x), math.floor(y)
        fx, fy = x - i, y - j
        u, v = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a, b = self._h(i, j), self._h(i + 1, j)
        c, d = self._h(i, j + 1), self._h(i + 1, j + 1)
        return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v

    def fbm(self, x, y, octaves=4):
        s, amp, tot = 0.0, 0.5, 0.0
        for _ in range(octaves):
            s += amp * self(x, y)
            tot += amp
            x, y, amp = x * 2.03, y * 2.03, amp * 0.5
        return s / tot


# ── data ────────────────────────────────────────────────────────────────────

QUERY = """query($login:String!){user(login:$login){createdAt
 contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}
 repositories(first:100,privacy:PUBLIC,ownerAffiliations:OWNER,isFork:false,orderBy:{field:PUSHED_AT,direction:DESC}){
  nodes{name url description stargazerCount primaryLanguage{name color}
   languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}}}"""


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return sample_data()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": LOGIN})
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]["user"]


def sample_data():
    r = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=today.weekday() + 1 + 52 * 7)
    days = [{"date": (start + dt.timedelta(d)).isoformat(),
             "contributionCount": int(r.random() ** 3 * 30) if r.random() < 0.5 else 0}
            for d in range((today - start).days + 1)]
    weeks = [{"contributionDays": days[i:i + 7]} for i in range(0, len(days), 7)]
    repo = lambda n, l, c, s: {"name": n, "url": f"https://github.com/{LOGIN}/{n}", "stargazerCount": s,
                               "description": "an example repository description for previewing the card",
                               "primaryLanguage": {"name": l, "color": c},
                               "languages": {"edges": [{"size": 1000, "node": {"name": l, "color": c}}]}}
    return {"createdAt": "2025-09-10T00:00:00Z",
            "contributionsCollection": {"contributionCalendar": {
                "totalContributions": sum(d["contributionCount"] for d in days), "weeks": weeks}},
            "repositories": {"nodes": [repo(FEATURED[0], "Python", "#3572A5", 3),
                                       repo(FEATURED[1], "Python", "#3572A5", 2),
                                       repo("game", "JavaScript", "#f1e05a", 1)]}}


def streaks(days):
    best = cur = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        best = max(best, run)
    # today may still be empty: count the streak up to yesterday then
    tail = days[:-1] if days and not days[-1]["contributionCount"] else days
    for d in reversed(tail):
        if not d["contributionCount"]:
            break
        cur += 1
    return cur, best


def moon_phase(when):
    """Fraction of the synodic month since new moon (0 new, .5 full)."""
    ref = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
    return ((when - ref).total_seconds() / 86400 / 29.530588853) % 1


def phase_name(p):
    names = ["new moon", "waxing crescent", "first quarter", "waxing gibbous",
             "full moon", "waning gibbous", "last quarter", "waning crescent"]
    return names[int((p * 8 + 0.5) % 8)]


# ── hero: ray-traced ringed planet + name ──────────────────────────────────

TITLE = """\
███████╗██╗███╗   ██╗ ██████╗
╚══███╔╝██║████╗  ██║██╔═══██╗
  ███╔╝ ██║██╔██╗ ██║██║   ██║
 ███╔╝  ██║██║╚██╗██║██║   ██║
███████╗██║██║ ╚████║╚██████╔╝
╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ """

RAMP = " .,:;-=+*#%@"
RING = " .-~=≡"


def planet_scene(cx, cy, frames, pal):
    cw, lh, fs = 5.4, 10.0, 9
    Rp = 80.0
    rin, rout = Rp * 1.3, Rp * 2.15
    cols, rows = int(2 * rout / cw) + 4, int(2 * Rp / lh) + 12
    ox, oy = cx - cols * cw / 2, cy - rows * lh / 2

    a, roll = math.radians(16), math.radians(-14)
    n = (0.0, -math.cos(a), -math.sin(a))
    n = norm((n[0] * math.cos(roll) - n[1] * math.sin(roll),
              n[0] * math.sin(roll) + n[1] * math.cos(roll), n[2]))
    e1 = norm(cross(n, (0, 0, 1)))
    e2 = cross(n, e1)
    L = norm((-0.58, -0.3, -0.76))
    noise = Noise(3)

    def ring_albedo(r):
        u = (r - rin) / (rout - rin)
        if not 0 <= u <= 1 or 0.6 < u < 0.67:
            return 0.0
        return max(0.0, 0.55 + 0.25 * math.sin(u * 31) + 0.2 * math.sin(u * 83) - 0.35 * max(0, u - 0.8) * 4)

    def ring_hit(p):
        r = math.sqrt(dot(p, p))
        return ring_albedo(r)

    ring = [[(" ", None)] * cols for _ in range(rows)]
    disc = []  # (j, i, point) cells where the planet is the nearest surface
    for j in range(rows):
        for i in range(cols):
            x, y = ox + (i + .5) * cw - cx, oy + (j + .5) * lh - cy
            zs = -math.sqrt(Rp * Rp - x * x - y * y) if x * x + y * y < Rp * Rp else None
            zr = -(n[0] * x + n[1] * y) / n[2]
            p = (x, y, zr)
            alb = ring_hit(p)
            if alb > 0 and (zs is None or zr < zs):
                b, c = dot(p, L), dot(p, p) - Rp * Rp
                lit = 0.25 if (b * b - c > 0 and b < 0) else 1.0
                lum = min(1.0, alb * lit * (0.75 + 0.5 * abs(dot(n, L))))
                k = min(len(RING) - 1, int(lum * len(RING)))
                if k:
                    ring[j][i] = (RING[k], pal(scale(mix("#7f78b0", "#fbecc8", lum), 0.4 + 0.7 * lum)))
            elif zs is not None:
                disc.append((j, i, (x, y, zs)))

    groups = []
    for f in range(frames):
        rot = 2 * math.pi * f / frames
        grid = [[(" ", None)] * cols for _ in range(rows)]
        for j, i, p in disc:
            N = tuple(c / Rp for c in p)
            lat = math.asin(max(-1, min(1, dot(N, n))))
            lon = math.atan2(dot(N, e2), dot(N, e1)) + rot
            diff = max(0.0, dot(N, L))
            t = -dot(n, p) / dot(n, L)
            if t > 0 and ring_hit(tuple(pc + t * lc for pc, lc in zip(p, L))) > 0:
                diff *= 0.6
            wob = noise.fbm(math.cos(lon) * 1.6 + 5, lat * 3 + math.sin(lon) * 1.6, 3)
            band = 0.5 + 0.5 * math.sin(lat * 11 + wob * 4)
            base = mix("#b8643a", "#f6dcaa", band)
            dl = (lon - 1.2 + math.pi) % (2 * math.pi) - math.pi
            spot = ((dl * math.cos(lat)) / 0.32) ** 2 + ((lat + 0.42) / 0.13) ** 2
            if spot < 1:
                base = mix("#e2502e", base, spot ** 2)
                band = 0.3 + 0.4 * spot
            lum = 0.05 + 0.95 * diff
            k = int(min(len(RAMP) - 1, (0.45 + 0.55 * band) * lum * 14))
            if lum < 0.12:
                ch, col = (".", "#2c2550") if (i + j) % 3 == 0 else (" ", None)
            else:
                q = round(lum * 7) / 7
                ch, col = RAMP[max(1, k)], scale(base, 0.35 + 0.8 * q)
            grid[j][i] = (ch, pal(col) if col else None)
        groups.append(f'<g class="f" font-weight="700" style="animation-delay:{f * 0.8:.1f}s">'
                      f'{art_rows(grid, ox, oy + lh * .8, cw, lh, fs)}</g>')

    occluder = f'<circle cx="{cx}" cy="{cy}" r="{Rp + 1.5}" fill="{BG0}"/>'
    glow = (f'<circle cx="{cx}" cy="{cy}" r="{Rp + 14}" fill="url(#halo)"/>')
    return (glow + occluder + "".join(groups) +
            art_rows(ring, ox, oy + lh * .8, cw, lh, fs, ' font-weight="700"'), frames * 0.8)


def starfield(rng, h, n, avoid=None, twinkle=0.35, region=(0, W)):
    out = []
    for _ in range(n):
        x, y = rng.uniform(*region), rng.uniform(8, h - 8)
        if avoid and avoid(x, y):
            continue
        r = rng.random()
        ch, size, col = ((".", 9, FAINT) if r < .45 else ("·", 10, DIM) if r < .75 else
                         ("+", 9, "#aab4d8") if r < .9 else ("*", 10, INK) if r < .97 else ("✶", 11, GOLD))
        col = rng.choice([col, col, "#9fb4ff", "#ffd9a8"]) if ch != "." else col
        anim = (f' style="animation:tw {rng.uniform(2.5, 6.5):.1f}s {rng.uniform(0, 6):.1f}s ease-in-out infinite"'
                if rng.random() < twinkle else "")
        out.append(f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" fill="{col}"{anim}>{ch}</text>')
    return "".join(out)


def nebula(h, seed, weight):
    noise, hue = Noise(seed), Noise(seed + 1)
    rng = random.Random(seed)
    dust = []
    for _ in range(2600):
        x, y = rng.random(), rng.random()
        v = noise.fbm(x * 4, y * 2.6, 5) * weight(x, y)
        if rng.random() > max(0, v - 0.42) * 1.4:
            continue
        c = scale(mix("#7b3fb0", "#1595a0", hue.fbm(x * 3, y * 3)), 0.5 + 0.5 * v)
        dust.append(f'<text x="{x * W:.0f}" y="{y * h:.0f}" font-size="9" fill="{c}">{rng.choice("..·:")}</text>')
    clouds = "".join(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#cloud{k})" opacity="{o}"/>'
                     for k, (cx, cy, rx, ry, o) in enumerate([(560, 90, 190, 60, .16), (760, 250, 150, 70, .16),
                                                              (420, 260, 140, 40, .08)]))
    return clouds + "".join(dust)


def shooting_star(x0, y0, dx, dy, dur, begin):
    ang = math.degrees(math.atan2(dy, dx))
    return (f'<g opacity="0"><g transform="rotate({ang:.0f})">'
            f'<line x1="-70" y1="0" x2="0" y2="0" stroke="url(#trail)" stroke-width="1.4"/>'
            f'<circle r="1.6" fill="#fff"/></g>'
            f'<animateTransform attributeName="transform" type="translate" values="{x0} {y0};{x0 + dx} {y0 + dy};{x0 + dx} {y0 + dy}" '
            f'keyTimes="0;.07;1" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;.01;.05;.07;1" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/></g>')


def hero():
    h = 320
    pal, rng = Palette("p"), random.Random(42)
    pcx, pcy = 640, 160
    planet, period = planet_scene(pcx, pcy, 24, pal)
    neb = nebula(h, 11, lambda x, y: max(0, min(1, (x - 0.3) * 2.5)) * min(1, (1 - x) * 8, y * 6, (1 - y) * 6))
    text_boxes = [(40, 18, 420, 40), (40, 52, 420, 196), (380, 160, 490, 190), (40, 208, 500, 290)]
    stars = starfield(rng, h, 170, avoid=lambda x, y: (x - pcx) ** 2 + (y - pcy) ** 2 < 80 ** 2 or
                      any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in text_boxes))

    # title: blocks get the gradient, the box-drawing "shadow" stays dim
    tx, ty, tfs, tcw, tlh = 44, 70, 19, 11.4, 21
    title = []
    for j, line in enumerate(TITLE.splitlines()):
        solid = "".join(c if c == "█" else " " for c in line)
        shade = "".join(c if c not in "█ " else " " for c in line)
        y = ty + j * tlh
        title.append(f'<text x="{tx}" y="{y}" font-size="{tfs}" fill="#36406a">{esc(shade.rstrip())}</text>')
        title.append(f'<text x="{tx}" y="{y}" font-size="{tfs}" fill="url(#title)" stroke="url(#title)" '
                     f'stroke-width="5" stroke-opacity=".13" stroke-linejoin="round">{esc(solid.rstrip())}</text>')
    tag = (f'<text x="{tx + 30 * tcw + 14}" y="{ty + 5 * tlh}" font-size="12" fill="{DIM}">@{LOGIN}</text>')

    # typed tagline, one clip per line
    lfs, lcw, llh = 14, 8.4, 24
    ly, start, per = ty + 6 * tlh + 30, 0.8, 0.045
    lines, clips = [], []
    for k, msg in enumerate(TAGLINES):
        y = ly + k * llh
        n = len(msg) + 2
        steps = ";".join(f"{c * lcw:.1f}" for c in range(n + 1))
        dur = n * per
        end = start + dur
        nxt = end + 0.35 if k < len(TAGLINES) - 1 else None
        clips.append(f'<clipPath id="ty{k}"><rect x="{tx}" y="{y - 16}" width="0" height="22">'
                     f'<animate attributeName="width" values="{steps}" calcMode="discrete" dur="{dur:.2f}s" '
                     f'begin="{start:.2f}s" fill="freeze"/></rect></clipPath>')
        lines.append(f'<text x="{tx}" y="{y}" font-size="{lfs}" clip-path="url(#ty{k})">'
                     f'<tspan fill="{PINK}">›</tspan><tspan fill="{INK}"> {esc(msg)}</tspan></text>')
        xs = ";".join(f"{tx + c * lcw:.1f}" for c in range(n + 1))
        blink = ' class="blink"' if nxt is None else ""
        lines.append(f'<rect y="{y - 12}" width="{lcw:.1f}" height="15" fill="{GOLD}" opacity="0"{blink}>'
                     f'<animate attributeName="x" values="{xs}" calcMode="discrete" dur="{dur:.2f}s" begin="{start:.2f}s" fill="freeze"/>'
                     f'<set attributeName="opacity" to=".85" begin="{start:.2f}s"/>'
                     + (f'<set attributeName="opacity" to="0" begin="{nxt:.2f}s"/>' if nxt else "") + "</rect>")
        start = nxt or start

    coords = (f'<text x="{tx}" y="34" font-size="10.5" fill="{FAINT}">'
              f'[ {esc(BASE[1])} · {esc(BASE[0])} ]   transmission open</text>')
    shooters = shooting_star(300, 20, 260, 95, 13, 4) + shooting_star(560, 8, 230, 80, 17, 10)

    defs = (BG_DEF +
            f'<linearGradient id="title" x1="{tx}" x2="{tx + 340}" y1="0" y2="0" gradientUnits="userSpaceOnUse" spreadMethod="reflect">'
            f'<stop offset="0" stop-color="{GOLD}"/><stop offset=".35" stop-color="{PINK}"/>'
            f'<stop offset=".7" stop-color="{VIOLET}"/><stop offset="1" stop-color="{CYAN}"/>'
            f'</linearGradient>'
            '<linearGradient id="trail"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#fff" stop-opacity=".9"/></linearGradient>'
            '<radialGradient id="halo"><stop offset=".55" stop-color="#f6c48a" stop-opacity=".10"/>'
            '<stop offset="1" stop-color="#f6c48a" stop-opacity="0"/></radialGradient>'
            + HAZE + "".join(clips))
    pct = 100 / 24
    css = (pal.css() +
           f".f{{opacity:0;animation:spin {period:.1f}s steps(1,end) infinite}}"
           f"@keyframes spin{{0%{{opacity:1}}{pct:.4f}%{{opacity:0}}100%{{opacity:0}}}}"
           "@keyframes tw{0%,100%{opacity:1}50%{opacity:.15}}"
           ".blink{animation:bl 1.1s steps(1,end) infinite 3s}@keyframes bl{50%{opacity:0}}")
    body = frame(h, neb + stars + shooters + planet + "".join(title) + tag + coords + "".join(lines))
    return doc(h, body, css, defs, weights=("regular", "bold"))


# ── the sky above zürich: contribution calendar as stars ───────────────────

# peaks as (column fraction, height in rows); flanks fall one row per column
FAR_ALPS = [(.02, 4, .6), (.12, 7, .9), (.2, 5, .7), (.3, 9, 1), (.36, 7, .8), (.5, 5, .5), (.59, 8, .9),
            (.65, 9, 1), (.71, 7, .8), (.84, 6, .6), (.95, 5, .7)]
NEAR_ALPS = [(.06, 3, .8), (.18, 2, .7), (.27, 4, .9), (.41, 3, .75), (.53, 2, .7), (.68, 4, .85),
             (.8, 2, .7), (.93, 3, .8)]


def alps(peaks, cols, cw, lh, ground, edge, fill, snow, snowline, pal, seed):
    """Classic /\\ ASCII range: ridge chars on top of an opaque silhouette."""
    H = [max(0, max(h - abs(e - p * cols) * sl for p, h, sl in peaks)) for e in range(cols + 1)]
    H = [round(h) for h in H]
    top = max(H) + 1
    grid = [[(" ", None)] * cols for _ in range(top)]
    rng = random.Random(seed)
    for i in range(cols):
        hl, hr = H[i], H[i + 1]
        if hr > hl:
            ch, r = "/", hl
        elif hr < hl:
            ch, r = "\\", hr
        else:
            ch, r = "_", hl
        if r >= top:
            continue
        grid[top - 1 - r][i] = (ch, pal(snow if r >= snowline else edge))
        for rr in range(r - 1, -1, -1):
            depth = r - rr
            if r >= snowline and depth == 1 and ch != "_":
                grid[top - 1 - rr][i] = (rng.choice(".'"), pal(snow))
            elif rng.random() < 0.07:
                grid[top - 1 - rr][i] = (rng.choice(".,'"), pal(edge))
    poly = " ".join(f"{e * cw:.1f},{ground - h * lh:.1f}" for e, h in enumerate(H))
    shape = f'<polygon points="0,{ground} {poly} {cols * cw:.1f},{ground}" fill="{fill}"/>'
    return shape + art_rows(grid, 0, ground - (top - 1) * lh - lh * .22, cw, lh, 10)


def moon(cx, cy, r, phase, pal):
    cw, lh, fs = 5.4, 9.6, 9
    th = 2 * math.pi * phase
    L = (math.sin(th), -0.08, math.cos(th))
    noise = Noise(5)
    cols, rows = int(2 * r / cw) + 2, int(2 * r / lh) + 2
    ox, oy = cx - cols * cw / 2, cy - rows * lh / 2
    grid = []
    for j in range(rows):
        row = []
        for i in range(cols):
            x, y = ox + (i + .5) * cw - cx, oy + (j + .5) * lh - cy
            if x * x + y * y >= r * r:
                row.append((" ", None))
                continue
            N = (x / r, y / r, -math.sqrt(max(0, 1 - (x * x + y * y) / (r * r))))
            lum = max(0.0, dot(N, L))
            mare = noise.fbm(x / r * 1.8 + 3, y / r * 1.8 + 3, 4)
            alb = 0.62 + (0.38 if mare < 0.5 else 0.1)
            v = lum * alb
            if v < 0.06:
                row.append(("." if (i + j) % 4 == 0 else " ", pal("#252a45")))
            else:
                k = min(len(RAMP) - 1, max(1, int(v * 12)))
                row.append((RAMP[k], pal(scale(mix("#9aa3c7", "#fff3d1", v), 0.4 + 0.75 * v))))
        grid.append(row)
    glow = f'<circle cx="{cx}" cy="{cy}" r="{r * 2.2}" fill="url(#moonglow)" opacity="{0.25 + 0.75 * (1 - math.cos(th)) / 2:.2f}"/>'
    disc = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{BG0}" opacity=".85"/>'
    return glow + disc + art_rows(grid, ox, oy + lh * .8, cw, lh, fs, ' font-weight="700"')


def sky(user, now):
    h = 310
    pal, rng = Palette("s"), random.Random(9)
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    counts = sorted(d["contributionCount"] for d in days if d["contributionCount"])
    q = lambda f: counts[min(len(counts) - 1, int(len(counts) * f))] if counts else 1
    t1, t2, t3 = q(0.4), q(0.75), q(0.93)

    x0, x1, y0, dy = 30, 664, 66, 14.5
    dx = (x1 - x0) / max(1, len(weeks) - 1)
    stars, pts, months = [], [], []
    last_month = None
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            day = dt.date.fromisoformat(d["date"])
            c = d["contributionCount"]
            dr = random.Random(d["date"])
            x = x0 + wi * dx + dr.uniform(-4, 4)
            y = y0 + ((day.weekday() + 1) % 7) * dy + dr.uniform(-4.5, 4.5)
            if day.day <= 7 and day.month != last_month and (day.weekday() + 1) % 7 == 0:
                months.append((x0 + wi * dx, day.strftime("%b").lower()))
                last_month = day.month
            if not c:
                if dr.random() < 0.3:
                    stars.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="8" fill="#252c48">.</text>')
                continue
            lvl = 0 if c < t1 else 1 if c < t2 else 2 if c < t3 else 3
            ch, fs, col = [("·", 11, "#6d7bb0"), ("+", 10, "#aeb9ec"), ("*", 12, "#eef0ff"), ("✶", 13, GOLD)][lvl]
            anim = (f' style="animation:tw {dr.uniform(2.5, 5.5):.1f}s {dr.uniform(0, 5):.1f}s ease-in-out infinite"'
                    if lvl >= 2 else "")
            glow = ""
            if lvl == 3:
                stars.append(f'<circle cx="{x:.1f}" cy="{y - 4:.1f}" r="9" fill="url(#starhalo)"/>')
            stars.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{fs}" fill="{col}" text-anchor="middle"{glow}{anim}>'
                         f'<title>{d["date"]}: {c} contribution{"s" * (c != 1)}</title>{esc(ch)}</text>')
            pts.append((c, d["date"], x, y - 3))

    # constellation: the brightest days, joined in time order
    top = sorted(sorted(pts, reverse=True)[:7], key=lambda p: p[1])
    const = ""
    if len(top) > 1:
        path = " ".join(f"{p[2]:.1f},{p[3]:.1f}" for p in top)
        const = (f'<polyline points="{path}" fill="none" stroke="{GOLD}" stroke-opacity=".22" '
                 f'stroke-width=".8" stroke-dasharray="2 3"/>')
        best = max(top)
        const += (f'<text x="{best[2] + 8:.1f}" y="{best[3] - 6:.1f}" font-size="9" fill="{GOLD}" opacity=".7">'
                  f'{best[0]} · {dt.date.fromisoformat(best[1]).strftime("%b %d").lower()}</text>')

    month_lbl = "".join(f'<text x="{mx:.0f}" y="{y0 - 16:.0f}" font-size="9" fill="{FAINT}">{m}</text>'
                        for mx, m in months[1:])

    # alps: a far range in violet, a near one in blue with snow on the peaks
    cw, lh = 6.0, 9.0
    cols = int(W / cw) + 1
    hz = 238
    mtn = (alps(FAR_ALPS, cols, cw, lh, hz, "#3d3a72", "#0c0d22", "#8f8cc4", 6, pal, 1) +
           alps(NEAR_ALPS, cols, cw, lh, hz + 2, "#4a5a94", "#080a18", "#dfe6ff", 4, pal, 2))

    # lake zürich, with the moon's light path on it
    phase = moon_phase(now)
    mx, my, mr = 752, 100, 48
    lake, lake_y = [], hz + 14
    shine = 0.35 + 0.6 * (1 - math.cos(2 * math.pi * phase)) / 2
    for j in range(4):
        y = lake_y + j * 11
        for i in range(cols):
            x = i * cw
            hw = 10 + j * 9
            if abs(x - mx) < hw and rng.random() < 0.8:
                lake.append(f'<text x="{x:.0f}" y="{y}" font-size="10" fill="{GOLD}" opacity="{shine * (1 - j * .15):.2f}" '
                            f'style="animation:tw {rng.uniform(1.5, 3.5):.1f}s {rng.uniform(0, 3):.1f}s infinite">'
                            f'{rng.choice("~-=~-")}</text>')
            elif rng.random() < 0.06:
                lake.append(f'<text x="{x:.0f}" y="{y}" font-size="10" fill="#28305a">{rng.choice("~-~_")}</text>')

    illum = (1 - math.cos(2 * math.pi * phase)) / 2
    total = cal["totalContributions"]
    cur, best_streak = streaks(days)
    head = (f'<text x="30" y="30" font-size="11" fill="{DIM}">the sky above zürich</text>'
            f'<text x="170" y="30" font-size="11" fill="{FAINT}">· every star is a day of commits</text>'
            f'<text x="{W - 30}" y="30" font-size="11" fill="{DIM}" text-anchor="end">'
            f'☾ {phase_name(phase)} · {illum * 100:.0f}%</text>')
    foot = (f'<text x="{W - 24}" y="{h - 14}" font-size="10" fill="{DIM}" text-anchor="end">'
            f'<tspan fill="{GOLD}">{total}</tspan> contributions · '
            f'streak <tspan fill="{INK}">{cur}d</tspan> · longest <tspan fill="{INK}">{best_streak}d</tspan></text>'
            f'<text x="24" y="{h - 14}" font-size="10" fill="{FAINT}">'
            f'<tspan fill="#6d7bb0">·</tspan> 1  <tspan fill="#aeb9ec">+</tspan> {t1}  '
            f'<tspan fill="#eef0ff">*</tspan> {t2}  <tspan fill="{GOLD}">✶</tspan> {t3}+</text>')

    bg_stars = starfield(rng, 215, 60, twinkle=0.1, avoid=lambda x, y: y < 40 or x > 690)
    defs = (BG_DEF.replace('cy="40%"', 'cy="0%"') +
            '<linearGradient id="horizon" x1="0" x2="0" y1="0" y2="1">'
            '<stop offset="0" stop-color="#3b2a6b" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#3b2a6b" stop-opacity=".35"/></linearGradient>'
            '<radialGradient id="moonglow"><stop offset=".35" stop-color="#fff3d1" stop-opacity=".18"/>'
            '<stop offset="1" stop-color="#fff3d1" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="starhalo"><stop offset="0" stop-color="#fde68a" stop-opacity=".35"/>'
            '<stop offset="1" stop-color="#fde68a" stop-opacity="0"/></radialGradient>')
    body = frame(h, f'<rect x="0" y="120" width="{W}" height="{hz - 110}" fill="url(#horizon)"/>' + bg_stars +
                 moon(mx, my, mr, phase, pal) + const + "".join(stars) + month_lbl + mtn +
                 f'<rect x="1" y="{hz + 4}" width="{W - 2}" height="{h - hz - 5}" fill="{BG0}" opacity=".55"/>'
                 + "".join(lake) + head + foot)
    css = pal.css() + "@keyframes tw{0%,100%{opacity:1}50%{opacity:.25}}"
    return doc(h, body, css, defs, weights=("regular", "bold"))


# ── telemetry readout ──────────────────────────────────────────────────────

SATELLITE = """\

                ◉
                │
 ┌──┬──┬──┐  ┌──┴──┐  ┌──┬──┬──┐
 ├──┼──┼──┤══╡ ▓▓▓ ╞══├──┼──┼──┤
 ├──┼──┼──┤  │ ▓▓▓ │  ├──┼──┼──┤
 └──┴──┴──┘  └──┬──┘  └──┴──┴──┘
               ═╧═"""


def languages(repos):
    mix_ = {}
    for r in repos:
        edges = [e for e in r["languages"]["edges"] if e["node"]["name"] not in SKIP_LANGS]
        tot = sum(e["size"] for e in edges)
        for e in edges:
            name, col = e["node"]["name"], e["node"]["color"] or DIM
            share = mix_.setdefault(name, [0.0, col])
            share[0] += e["size"] / tot
    tot = sum(v[0] for v in mix_.values()) or 1
    return sorted(((k, v[0] / tot, v[1]) for k, v in mix_.items()), key=lambda t: -t[1])


def telemetry(user, now):
    h = 336
    repos = user["repositories"]["nodes"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    cur, best = streaks(days)
    created = dt.datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
    sol = (now - created).days
    stars = sum(r["stargazerCount"] for r in repos)

    # ascii frame around the whole readout
    bcw, bx0, bx1 = 6.6, 20, W - 20
    inner = int((bx1 - bx0) / bcw) - 2
    title = f" telemetry · {NAME}@{LOGIN} "
    stamp = f" last contact {now:%Y-%m-%d %H:%M} utc "
    out = [f'<text x="{bx0}" y="30" font-size="11" fill="{FAINT}">╭─<tspan fill="{DIM}">{esc(title)}</tspan>'
           f'{"─" * (inner - len(title) - 1)}╮</text>',
           f'<text x="{bx0}" y="{h - 16}" font-size="11" fill="{FAINT}">╰{"─" * (inner - len(stamp) - 4)}'
           f'<tspan fill="{DIM}">{esc(stamp)}</tspan><tspan fill="{GOLD}" class="blink">▮</tspan>──╯</text>']
    for y in range(44, h - 22, 14):
        out.append(f'<text x="{bx0}" y="{y}" font-size="11" fill="{FAINT}">│</text>'
                   f'<text x="{bx0 + (inner + 1) * bcw:.1f}" y="{y}" font-size="11" fill="{FAINT}">│</text>')

    # satellite with a pulsing dish
    sx, sy, scw, slh = 46, 62, 7.2, 15
    for j, line in enumerate(SATELLITE.splitlines()):
        out.append(f'<text x="{sx}" y="{sy + j * slh}" font-size="12" fill="#8f9cc9">{esc(line)}</text>')
    dish = (sx + 16 * scw, sy + slh)
    out.append(f'<text x="{dish[0]:.1f}" y="{dish[1]}" font-size="12" fill="{PINK}" '
               f'style="animation:pulse 1.6s infinite">◉</text>')
    for k in range(3):
        out.append(f'<text x="{dish[0] + (3 + 3 * k) * scw:.1f}" y="{dish[1] - 2}" font-size="13" fill="{CYAN}" '
                   f'style="animation:pulse 2.4s {k * .35:.2f}s ease-out infinite">)</text>')
    out.append(f'<text x="{sx}" y="{sy + 9 * slh + 4}" font-size="10" fill="{FAINT}">'
               f'orbit {esc("·  ˙  ·  .  ·  ˙  ·  .  ·  ˙  ·")}</text>')

    rows = [
        ("callsign", [(NAME, INK), (f"  @{LOGIN}", DIM)]),
        ("base", [(BASE[0], INK), (f"  {BASE[1]}", DIM)]),
        ("crew", [(CREW, INK)]),
        ("vessel", [(VESSEL, INK)]),
        ("mission day", [(str(sol), GOLD), (f"  since {created:%Y-%m-%d}", DIM)]),
        ("signal", [(str(cal["totalContributions"]), GOLD), (" contributions in 365 days", INK)]),
        ("streak", [(f"{cur} day{'s' * (cur != 1)}", INK), (f"  longest {best}", DIM)]),
        ("satellites", [(str(len(repos)), GOLD), (" public repos · ", INK), (str(stars), GOLD), (" stars", INK)]),
    ]
    tx, ty, tlh = 330, 64, 21
    for k, (label, vals) in enumerate(rows):
        dots = "." * (13 - len(label))
        spans = "".join(f'<tspan fill="{c}">{esc(t)}</tspan>' for t, c in vals)
        out.append(f'<text x="{tx}" y="{ty + k * tlh}" font-size="12.5"><tspan fill="{CYAN}">{label}</tspan>'
                   f'<tspan fill="{FAINT}"> {dots} </tspan>{spans}</text>')

    # fuel mix: one stacked bar of block characters, legend underneath
    langs = languages(repos)
    top = [l for l in langs[:6] if l[1] >= 0.01]
    rest = 1 - sum(l[1] for l in top)
    if rest >= 0.005:
        top.append(("other", rest, FAINT))
    fx, fy, fcw, cells = 46, 262, 6.6, 113
    out.append(f'<text x="{fx}" y="{fy - 18}" font-size="11" fill="{CYAN}">fuel mix'
               f'<tspan fill="{FAINT}"> ......... </tspan><tspan fill="{DIM}">languages, weighted per repo</tspan></text>')
    bar, used = [], 0
    for k, (name, share, col) in enumerate(top):
        n = cells - used if k == len(top) - 1 else round(share * cells)
        bar.append(f'<tspan fill="{col}">{"█" * n}</tspan>')
        used += n
    out.append(f'<text x="{fx}" y="{fy}" font-size="11">{"".join(bar)}</text>')
    lx = fx
    for name, share, col in top:
        label = f"{name.lower()} {share * 100:.0f}%"
        out.append(f'<text x="{lx:.0f}" y="{fy + 22}" font-size="11"><tspan fill="{col}">●</tspan>'
                   f'<tspan fill="{DIM}"> {esc(label)}</tspan></text>')
        lx += (len(label) + 5) * fcw

    css = ("@keyframes pulse{0%{opacity:.15}30%{opacity:1}100%{opacity:.15}}"
           ".blink{animation:bl 1.1s steps(1,end) infinite}@keyframes bl{50%{opacity:0}}"
           "@keyframes tw{0%,100%{opacity:1}50%{opacity:.15}}")
    rng = random.Random(5)
    field = starfield(rng, h, 40, avoid=lambda x, y: x > 320 and y < 230 or y > 230, twinkle=0.3)
    return doc(h, frame(h, field + "".join(out)), css, BG_DEF)


# ── mission cards ──────────────────────────────────────────────────────────

def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur] if cur else lines


def card(repo, idx):
    w, h = 410, 150
    lang = repo["primaryLanguage"] or {"name": "-", "color": DIM}
    desc = wrap((repo["description"] or "").lower(), 50)[:4]
    rng = random.Random(repo["name"])
    title = repo["name"]
    out = [f'<text x="20" y="32" font-size="10.5" fill="{FAINT}">mission {idx:02d}</text>',
           f'<text x="20" y="54" font-size="17" font-weight="700" fill="{INK}">{esc(title)}</text>',
           f'<text x="{w - 20}" y="32" font-size="11" fill="{GOLD}" text-anchor="end">✶ {repo["stargazerCount"]}</text>']
    for k, line in enumerate(desc):
        out.append(f'<text x="20" y="{80 + k * 16}" font-size="11.5" fill="{DIM}">{esc(line)}</text>')
    out.append(f'<text x="20" y="{h - 16}" font-size="11"><tspan fill="{lang["color"] or DIM}">●</tspan>'
               f'<tspan fill="{INK}"> {esc(lang["name"].lower())}</tspan></text>'
               f'<text x="{w - 20}" y="{h - 16}" font-size="11" fill="{CYAN}" text-anchor="end">launch ↗</text>')
    # a small orbit in the corner: a planet char with a moon circling it
    ox, oy = w - 52, 72
    orbit = (f'<ellipse cx="{ox}" cy="{oy}" rx="22" ry="7" fill="none" stroke="{FAINT}" stroke-dasharray="1.5 3"/>'
             f'<text x="{ox}" y="{oy + 5}" font-size="15" fill="{rng.choice([GOLD, PINK, VIOLET, CYAN])}" text-anchor="middle">●</text>'
             f'<circle r="2" fill="{INK}"><animateMotion dur="{rng.uniform(5, 8):.1f}s" repeatCount="indefinite" '
             f'path="M{ox + 22},{oy} A22,7 0 1,1 {ox - 22},{oy} A22,7 0 1,1 {ox + 22},{oy}"/></circle>')
    stars = starfield(rng, h, 22, twinkle=0.3, region=(0, w), avoid=lambda x, y: (x < w - 64 and y > 18) or y > h - 28)
    bg = (f'<rect width="{w}" height="{h}" rx="12" fill="url(#bg)"/>{stars}{orbit}{"".join(out)}'
          f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="none" stroke="#1d2440"/>')
    svg = doc(h, bg, "@keyframes tw{0%,100%{opacity:1}50%{opacity:.15}}", BG_DEF, weights=("regular", "bold"))
    return svg.replace(f'viewBox="0 0 {W} {h}" width="{W}"', f'viewBox="0 0 {w} {h}" width="{w}"')


# ── footer: a little rocket on its way out ─────────────────────────────────

ROCKET = ["  __", " |  \\___", "=|___<>_)>", "    |/"]


def footer():
    h = 90
    rng = random.Random(77)
    rocket = "".join(f'<text x="0" y="{j * 11}" font-size="11" fill="{INK}">{esc(l)}</text>'
                     for j, l in enumerate(ROCKET))
    flame = (f'<text x="-22" y="22" font-size="11" fill="{GOLD}" class="fl1">~=-</text>'
             f'<text x="-22" y="22" font-size="11" fill="{PINK}" class="fl2">-~=</text>')
    ship = (f'<g>{flame}{rocket}<animateTransform attributeName="transform" type="translate" '
            f'values="-120 30;{W + 40} 30" dur="16s" repeatCount="indefinite"/></g>')
    msg = (f'<text x="{W / 2}" y="{h - 14}" font-size="11" fill="{FAINT}" text-anchor="middle">'
           f'·  ·  ·   end of transmission   ·  ·  ·</text>')
    css = ("@keyframes tw{0%,100%{opacity:1}50%{opacity:.15}}"
           ".fl1{animation:fl .24s steps(1,end) infinite}.fl2{animation:fl .24s .12s steps(1,end) infinite}"
           "@keyframes fl{50%{opacity:0}}")
    return doc(h, frame(h, starfield(rng, h, 50, twinkle=0.3) + ship + msg), css, BG_DEF)


def main():
    OUT.mkdir(exist_ok=True)
    user = fetch()
    now = dt.datetime.now(dt.timezone.utc)
    files = {"hero.svg": hero(), "sky.svg": sky(user, now), "telemetry.svg": telemetry(user, now),
             "footer.svg": footer()}
    by_name = {r["name"]: r for r in user["repositories"]["nodes"]}
    for i, name in enumerate(FEATURED, 1):
        if name in by_name:
            files[f"mission-{name}.svg"] = card(by_name[name], i)
    for name, svg in files.items():
        (OUT / name).write_text(svg)
        print(f"{name:28} {len(svg) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
