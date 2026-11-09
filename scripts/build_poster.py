"""Render the 36 x 24 in print poster for Detroit Wheels (poster/poster.svg + poster/poster.html)."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "poster"

W, H = 3600, 2400  # 1 unit = 0.01 in
BG, INK, MUTED, RULE = "#fafaf7", "#15171a", "#5f6670", "#e6e6e1"
CRASH, SLOW = "#e0245e", "#2a9d8f"
REACH = ["#f3f3ee", "#dcebe2", "#b5d8c4", "#7fbf9c", "#3f9b6f"]
LINE = {  # color, width, dash
    "shared": ("#9aa3ad", 4, "8 8"), "lane": ("#2f6fdb", 7, None), "path": ("#e07a1f", 10, None), "protected": ("#0b7a4b", 11, None),
    "jlg_planned": ("#7b2cbf", 8, "3 14"), "jlg_building": ("#7b2cbf", 11, "22 14"), "jlg_open": ("#7b2cbf", 14, None),
}
VENUE = (-83.1555, 42.4178)

hoods = json.loads((DATA / "neighborhoods.geojson").read_text())["features"]
network = json.loads((DATA / "network.geojson").read_text())["features"]
crashes = json.loads((DATA / "crashes.geojson").read_text())["features"]
S = json.loads((DATA / "summary.json").read_text())


def polys(g):
    return g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]


xs = [x for h in hoods for p in polys(h["geometry"]) for r in p for x, _ in r]
ys = [y for h in hoods for p in polys(h["geometry"]) for r in p for _, y in r]
lon0, lon1, lat0, lat1 = min(xs), max(xs), min(ys), max(ys)
kx = math.cos(math.radians((lat0 + lat1) / 2))
MX, MY, MW, MH = 120, 150, 2280, 2050
scale = min(MW / ((lon1 - lon0) * kx), MH / (lat1 - lat0))
ox = MX + (MW - (lon1 - lon0) * kx * scale) / 2
oy = MY + (MH - (lat1 - lat0) * scale) / 2


def proj(lon, lat):
    return ox + (lon - lon0) * kx * scale, oy + (lat1 - lat) * scale


def pts(coords):
    return "L".join(f"{x:.1f},{y:.1f}" for x, y in (proj(*c[:2]) for c in coords))


def reach_fill(r):
    return REACH[0 if r == 0 else 1 if r < 10 else 2 if r < 25 else 3 if r < 75 else 4]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


parts = []
add = parts.append
for h in hoods:
    d = "".join("M" + pts(ring) + "Z" for p in polys(h["geometry"]) for ring in p)
    add(f'<path d="{d}" fill="{reach_fill(h["properties"]["reach"])}" stroke="#ffffff" stroke-width="2.5"/>')

# White casing under every route makes the network read like a transit map.
for casing in (True, False):
    for f in network:
        color, width, dash = LINE[f["properties"]["cls"]]
        d = "".join("M" + pts(l) for l in f["geometry"]["coordinates"])
        if casing:
            add(f'<path d="{d}" fill="none" stroke="#ffffff" stroke-width="{width + 6}" stroke-linecap="round" stroke-linejoin="round"/>')
        else:
            add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"{f" stroke-dasharray={chr(34)}{dash}{chr(34)}" if dash else ""}/>')

for f in sorted(crashes, key=lambda c: c["properties"]["fatal"] + c["properties"]["serious"]):
    x, y = proj(*f["geometry"]["coordinates"])
    p = f["properties"]
    if p["fatal"]:
        add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="15" fill="{CRASH}" stroke="#fff" stroke-width="4"/><circle cx="{x:.1f}" cy="{y:.1f}" r="24" fill="none" stroke="{CRASH}" stroke-width="2.5"/>')
    elif p["serious"]:
        add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="{CRASH}" stroke="#fff" stroke-width="3"/>')
    else:
        add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{CRASH}" fill-opacity=".7"/>')

vx, vy = proj(*VENUE)
add(f'<circle cx="{vx:.1f}" cy="{vy:.1f}" r="16" fill="#fff" stroke="{INK}" stroke-width="6"/>')
add(f'<text x="{vx + 30:.1f}" y="{vy - 24:.1f}" class="callout">You are here · Marygrove Conservancy</text>')

sb = 5 * scale / 69.17
sx, sy = MX + 40, MY + MH - 30
add(f'<path d="M{sx},{sy}h{sb:.1f}" stroke="{INK}" stroke-width="4"/>' + "".join(f'<path d="M{sx + sb * i / 5:.1f},{sy - 10}v20" stroke="{INK}" stroke-width="3"/>' for i in range(6)))
add(f'<text x="{sx}" y="{sy - 22}" class="small">0</text><text x="{sx + sb:.1f}" y="{sy - 22}" class="small" text-anchor="end">5 miles</text>')
add(f'<path d="M{sx + sb + 90:.1f},{sy + 10}l18,-60l18,60l-18,-14z" fill="{INK}"/><text x="{sx + sb + 108:.1f}" y="{sy + 44}" class="small" text-anchor="middle">N</text>')

# Story column
CX, CW = 2560, W - 2560 - 120
add(f'<rect x="{CX - 70}" y="0" width="{W - CX + 70}" height="{H}" fill="#ffffff"/>')
y = 190
add(f'<text x="{CX}" y="{y}" class="kicker">DETROIT GIS DAY · NOVEMBER 18, 2026</text>')
y += 190
add(f'<text x="{CX}" y="{y}" class="title">Detroit</text>')
y += 165
add(f'<text x="{CX}" y="{y}" class="title">Wheels</text>')
y += 50
stripe = [("#0b7a4b", .22), ("#e07a1f", .18), ("#2f6fdb", .30), ("#7b2cbf", .18), (CRASH, .12)]
sx2 = CX
for c, w in stripe:
    add(f'<rect x="{sx2:.1f}" y="{y}" width="{CW * w:.1f}" height="18" fill="{c}"/>')
    sx2 += CW * w
y += 90


def para(text, y, cls, chars, lh):
    line = ""
    for w in text.split():
        if len(line) + len(w) + 1 > chars:
            add(f'<text x="{CX}" y="{y}" class="{cls}">{esc(line)}</text>')
            y += lh
            line = w
        else:
            line = f"{line} {w}".strip()
    add(f'<text x="{CX}" y="{y}" class="{cls}">{esc(line)}</text>')
    return y + lh


y = para("The Motor City is building a bike network. Here's how far it reaches, where the Joe Louis Greenway stands, and where riders still get hurt.", y, "dek", 46, 48)
y += 40

def half_up(x):  # match the web map, which rounds .5 up
    return int(x + 0.5)


stats = [(f"{half_up(S['dedicated_miles'])}", ("miles of dedicated", "bike routes"), INK),
         (f"{half_up(S['city_reach_pct'])}%", ("of Detroit is within", "¼ mile of one"), "#0b7a4b"),
         (f"{half_up(S['pct_off_facility'])}%", ("of bike crashes happened", "more than 100 ft from one"), CRASH)]
for big, (l1, l2), color in stats:
    add(f'<text x="{CX}" y="{y + 100}" class="big" fill="{color}">{big}</text>')
    add(f'<text x="{CX + 340}" y="{y + 58}" class="label">{esc(l1)}</text><text x="{CX + 340}" y="{y + 98}" class="label">{esc(l2)}</text>')
    y += 140
y += 40

add(f'<text x="{CX}" y="{y}" class="h3">THE NETWORK</text>')
y += 50
for k in ("protected", "path", "lane", "shared"):
    color, width, dash = LINE[k]
    add(f'<path d="M{CX},{y - 10}h70" stroke="{color}" stroke-width="{width}" stroke-linecap="round"{f" stroke-dasharray={chr(34)}{dash}{chr(34)}" if dash else ""}/>')
    add(f'<text x="{CX + 100}" y="{y}" class="body">{S["labels"][k]}</text><text x="{CX + CW}" y="{y}" class="body-b" text-anchor="end">{round(S["miles"][k])} mi</text>')
    y += 50
y += 40

add(f'<text x="{CX}" y="{y}" class="h3">JOE LOUIS GREENWAY</text>')
y += 50
for k, lbl in (("jlg_open", "Open"), ("jlg_building", "Under construction"), ("jlg_planned", "Funded or planned")):
    color, width, dash = LINE[k]
    add(f'<path d="M{CX},{y - 10}h70" stroke="{color}" stroke-width="{width}" stroke-linecap="round"{f" stroke-dasharray={chr(34)}{dash}{chr(34)}" if dash else ""}/>')
    add(f'<text x="{CX + 100}" y="{y}" class="body">{lbl}</text><text x="{CX + CW}" y="{y}" class="body-b" text-anchor="end">{S["jlg_miles"][k]} mi</text>')
    y += 50
y += 40

add(f'<text x="{CX}" y="{y}" class="h3">BIKE CRASHES, {S["crash_years"]}</text>')
y += 54
add(f'<circle cx="{CX + 35}" cy="{y - 10}" r="7" fill="{CRASH}" fill-opacity=".7"/><text x="{CX + 100}" y="{y}" class="body">{S["crashes"]} crashes involving a bicyclist</text>')
y += 54
add(f'<circle cx="{CX + 35}" cy="{y - 10}" r="12" fill="{CRASH}"/><text x="{CX + 100}" y="{y}" class="body">{S["serious"]} serious injuries</text>')
y += 58
add(f'<circle cx="{CX + 35}" cy="{y - 10}" r="15" fill="{CRASH}"/><circle cx="{CX + 35}" cy="{y - 10}" r="24" fill="none" stroke="{CRASH}" stroke-width="2.5"/><text x="{CX + 100}" y="{y}" class="body">{S["fatal"]} people killed</text>')
y += 80

add(f'<text x="{CX}" y="{y}" class="h3">SHARE OF NEIGHBORHOOD WITHIN ¼ MILE</text>')
y += 28
bw = CW / 5
for i, (c, t) in enumerate(zip(REACH, ["0", "<10%", "10–25%", "25–75%", "75%+"])):
    add(f'<rect x="{CX + i * bw:.1f}" y="{y}" width="{bw - 6:.1f}" height="30" fill="{c}" stroke="{RULE}"/><text x="{CX + i * bw:.1f}" y="{y + 62}" class="small">{t}</text>')
y += 80
assert y < H - 40, f"story column overflows: {y}"

foot = ("Data: City of Detroit Open Data Portal (data.detroitmi.gov): Bike Lanes, Joe Louis Greenway Route Segments, Traffic Crashes (bicycle-involved), "
        "Current City of Detroit Neighborhoods. Dedicated routes are painted, buffered and protected lanes, shared-use paths, and open Greenway segments; "
        "shared-lane markings are shown but not counted. Miles are summed per recorded segment. \"Away from one\" means more than 100 ft from a dedicated route.")
lines, line = [], ""
for w in foot.split():
    if len(line) + len(w) + 1 > 200:
        lines.append(line)
        line = w
    else:
        line = f"{line} {w}".strip()
lines.append(line)
fy = H - 150
for i, l in enumerate(lines):
    add(f'<text x="{MX}" y="{fy + i * 32}" class="foot">{esc(l)}</text>')
add(f'<text x="{MX}" y="{fy + len(lines) * 32}" class="foot" fill="{INK}">Interactive map: tamaraqawasmeh.github.io/detroit-wheels</text>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="36in" height="24in">
<defs><style>
  .kicker {{ font: 600 28px Inter, sans-serif; letter-spacing: 6px; fill: {MUTED}; }}
  .title {{ font: 700 190px "Space Grotesk", sans-serif; fill: {INK}; letter-spacing: -6px; }}
  .dek {{ font: 400 35px Inter, sans-serif; fill: {MUTED}; }}
  .big {{ font: 700 120px "Space Grotesk", sans-serif; letter-spacing: -3px; }}
  .label {{ font: 500 32px Inter, sans-serif; fill: {INK}; }}
  .h3 {{ font: 600 25px Inter, sans-serif; letter-spacing: 4px; fill: {MUTED}; }}
  .body {{ font: 400 30px Inter, sans-serif; fill: {INK}; }}
  .body-b {{ font: 700 30px "Space Grotesk", sans-serif; fill: {INK}; }}
  .small {{ font: 400 23px Inter, sans-serif; fill: {MUTED}; }}
  .callout {{ font: 700 34px "Space Grotesk", sans-serif; fill: {INK}; paint-order: stroke; stroke: #fff; stroke-width: 9px; }}
  .foot {{ font: 400 22px Inter, sans-serif; fill: {MUTED}; }}
</style></defs>
<rect width="{W}" height="{H}" fill="{BG}"/>
{"".join(parts)}
</svg>'''

OUT.mkdir(exist_ok=True)
(OUT / "poster.svg").write_text(svg, encoding="utf-8")
(OUT / "poster.html").write_text(f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Detroit Wheels · Poster</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&display=block" rel="stylesheet">
<style>@page {{ size: 36in 24in; margin: 0; }} html, body {{ margin: 0; background: {BG}; }} svg {{ display: block; width: 36in; height: 24in; }}
@media screen {{ svg {{ width: 100vw; height: auto; }} }}</style>
</head><body>{svg}</body></html>''', encoding="utf-8")
print("wrote poster", len(svg) // 1024, "KB")
