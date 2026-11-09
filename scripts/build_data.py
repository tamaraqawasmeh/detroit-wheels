"""Build the Detroit Wheels datasets from data/raw (see fetch_data.py).

Outputs:
  data/network.geojson        bike facilities and Joe Louis Greenway segments, one class per line
  data/neighborhoods.geojson  share of each neighborhood within a quarter mile of a dedicated facility
  data/crashes.geojson        bicycle-involved crashes 2020-2024 with distance to the nearest facility
  data/points.geojson         MoGo stations and repair stations
  data/calm.geojson           Slow Streets (traffic calming) and Safe Streets corridors
  data/summary.json           citywide numbers used in the story

Standard library only.
"""
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data"

QUARTER_MILE = 402.3  # meters
AT_FACILITY = 30.0    # a crash within ~100 ft of a facility counts as "on" it
GRID = 150.0          # meters between sample points when measuring neighborhood reach

# Class order is drawing order (bottom to top) and legend order (reversed).
LANE_CLASS = {
    "Shared Lane Marking": "shared", "Signed Route": "shared",
    "Bike Lane": "lane", "Buffered Bike Lane": "lane",
    "Protected Bike Lane": "protected",
    "Shared-Use Paths": "path",
}
JLG_CLASS = {"Open": "jlg_open", "Under Construction": "jlg_building", "Funded": "jlg_planned", "Unfunded": "jlg_planned"}
DEDICATED = {"lane", "protected", "path", "jlg_open"}
LABELS = {
    "protected": "Protected bike lane", "path": "Shared-use path", "lane": "Painted bike lane",
    "shared": "Shared lane / signed route", "jlg_open": "Joe Louis Greenway · open",
    "jlg_building": "Joe Louis Greenway · under construction", "jlg_planned": "Joe Louis Greenway · funded or planned",
}

LAT0 = 42.36
KX = 111320 * math.cos(math.radians(LAT0))
KY = 110540


def xy(lon, lat):
    return lon * KX, lat * KY


def load(name):
    return json.loads((RAW / f"{name}.geojson").read_text())["features"]


def lines(g):
    if not g:
        return []
    return [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"] if g["type"] == "MultiLineString" else []


def miles(coords):
    return sum(math.dist(xy(*a[:2]), xy(*b[:2])) for a, b in zip(coords, coords[1:])) / 1609.34


def seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


class SegmentIndex:
    """Grid buckets of line segments in local meters, for fast nearest-distance queries."""

    def __init__(self, segments, cell=QUARTER_MILE):
        self.cell, self.buckets = cell, defaultdict(list)
        for seg in segments:
            (ax, ay), (bx, by) = seg
            for i in range(int(min(ax, bx) // cell), int(max(ax, bx) // cell) + 1):
                for j in range(int(min(ay, by) // cell), int(max(ay, by) // cell) + 1):
                    self.buckets[(i, j)].append(seg)

    def nearest(self, p, radius):
        """Distance to the nearest segment, or None if nothing is within `radius` cells."""
        ci, cj = int(p[0] // self.cell), int(p[1] // self.cell)
        best = None
        for i in range(ci - radius, ci + radius + 1):
            for j in range(cj - radius, cj + radius + 1):
                for a, b in self.buckets.get((i, j), ()):
                    d = seg_dist(p, a, b)
                    if best is None or d < best:
                        best = d
        return best


def point_in_ring(pt, ring):
    x, y = pt
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def polys(g):
    return g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]


def contains(g, pt):
    return any(point_in_ring(pt, p[0]) and not any(point_in_ring(pt, h) for h in p[1:]) for p in polys(g))


def rnd(c):
    return [round(c[0], 5), round(c[1], 5)] if isinstance(c[0], (int, float)) else [rnd(x) for x in c]


def build():
    network = []
    for f in load("bike_lanes"):
        cls = LANE_CLASS.get(f["properties"]["on_road_type"])
        if cls and lines(f["geometry"]):
            p = f["properties"]
            network.append({"cls": cls, "name": p.get("route_name") or "", "detail": p.get("protected_bike_lane_type") or "", "lines": lines(f["geometry"])})
    for f in load("jlg"):
        cls = JLG_CLASS.get(f["properties"]["PHASE_DESCRIPTION"])
        if cls and lines(f["geometry"]):
            network.append({"cls": cls, "name": f["properties"]["ROUTE_SEGMENT_NAME"] or "Joe Louis Greenway", "detail": f["properties"]["TYPOLOGY"] or "", "lines": lines(f["geometry"])})

    miles_by = defaultdict(float)
    for n in network:
        miles_by[n["cls"]] += sum(miles(l) for l in n["lines"])

    segments = [(xy(*a[:2]), xy(*b[:2])) for n in network if n["cls"] in DEDICATED for l in n["lines"] for a, b in zip(l, l[1:])]
    index = SegmentIndex(segments)

    # Neighborhood reach: share of a regular grid of sample points inside each neighborhood within 1/4 mile.
    hoods = []
    for h in load("neighborhoods"):
        g = h["geometry"]
        pts = [c for p in polys(g) for c in p[0]]
        x0, y0 = xy(min(c[0] for c in pts), min(c[1] for c in pts))
        x1, y1 = xy(max(c[0] for c in pts), max(c[1] for c in pts))
        inside = near = 0
        y = y0 + GRID / 2
        while y < y1:
            x = x0 + GRID / 2
            while x < x1:
                lonlat = (x / KX, y / KY)
                if contains(g, lonlat):
                    inside += 1
                    d = index.nearest((x, y), 1)
                    if d is not None and d <= QUARTER_MILE:
                        near += 1
                x += GRID
            y += GRID
        reach = round(100 * near / inside, 1) if inside else 0.0
        hoods.append({"type": "Feature", "geometry": {"type": g["type"], "coordinates": rnd(g["coordinates"])},
                      "properties": {"name": h["properties"]["nhood_name"], "district": h["properties"]["council_district"], "reach": reach, "samples": inside}})

    crashes = []
    for f in load("bike_crashes"):
        if not f.get("geometry"):
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        d = index.nearest(xy(lon, lat), 3)
        p = f["properties"]
        crashes.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
                        "properties": {"date": p["crash_date"], "road": " & ".join(r.title() for r in (p["primary_road"], p["intersecting_road"]) if r),
                                       "fatal": p["num_fatal_injuries"] or 0, "serious": p["num_suspected_serious_injuries"] or 0,
                                       "ft_to_facility": round(d * 3.281) if d is not None else None}})

    for c in crashes:
        n = sum(1 for h in hoods if contains(h["geometry"], c["geometry"]["coordinates"]))
        c["properties"]["in_city"] = n > 0

    points = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": rnd(f["geometry"]["coordinates"][:2])},
               "properties": {"kind": "mogo", "name": f["properties"]["station_name"]}} for f in load("mogo") if f.get("geometry")]
    points += [{"type": "Feature", "geometry": {"type": "Point", "coordinates": rnd(f["geometry"]["coordinates"][:2])},
                "properties": {"kind": "repair", "name": f["properties"]["STATION_NAME"]}} for f in load("repair") if f.get("geometry") and f["properties"]["STATUS"] == "Installed"]

    slow = [rnd(l) for f in load("slow_streets") for l in lines(f["geometry"])]
    safe = [{"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": [rnd(l) for l in lines(f["geometry"])]},
             "properties": {"kind": "safe", "name": f["properties"]["street_name"], "extent": f["properties"]["corridor_extents"],
                            "scope": f["properties"]["scope_type"], "status": f["properties"]["status"]}} for f in load("safe_streets") if lines(f["geometry"])]
    calm = [{"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": slow}, "properties": {"kind": "slow"}}] + safe

    in_city = [c for c in crashes if c["properties"]["in_city"]]
    far = [c for c in in_city if c["properties"]["ft_to_facility"] is None or c["properties"]["ft_to_facility"] > AT_FACILITY * 3.281]
    reach_sorted = sorted((h["properties"] for h in hoods if h["properties"]["samples"] >= 10), key=lambda p: p["reach"])
    total_samples = sum(h["properties"]["samples"] for h in hoods)
    city_reach = sum(h["properties"]["reach"] * h["properties"]["samples"] for h in hoods) / total_samples
    zero = sum(1 for p in reach_sorted if p["reach"] == 0)
    summary = {
        "miles": {k: round(v, 1) for k, v in miles_by.items()},
        "labels": LABELS,
        "dedicated_miles": round(sum(v for k, v in miles_by.items() if k in DEDICATED), 1),
        "jlg_miles": {k: round(miles_by[k], 1) for k in ("jlg_open", "jlg_building", "jlg_planned")},
        "city_reach_pct": round(city_reach, 1),
        "zero_reach_hoods": zero,
        "neighborhoods": len(hoods),
        "best": [{"name": p["name"], "reach": p["reach"]} for p in reach_sorted[::-1][:5]],
        "crashes": len(crashes),
        "crashes_in_city": len(in_city),
        "crash_years": "2020–2024",
        "fatal": sum(c["properties"]["fatal"] for c in crashes),
        "serious": sum(c["properties"]["serious"] for c in crashes),
        "crashes_off_facility": len(far),
        "pct_off_facility": round(100 * len(far) / len(in_city), 1),
        "mogo": sum(1 for p in points if p["properties"]["kind"] == "mogo"),
        "repair": sum(1 for p in points if p["properties"]["kind"] == "repair"),
        "slow_segments": len(slow),
        "safe_corridors": len(safe),
        "breaks": [10, 25, 75],
    }

    def dump(name, obj):
        (OUT / name).write_text(json.dumps(obj, separators=(",", ":")))

    order = ["shared", "lane", "path", "protected", "jlg_planned", "jlg_building", "jlg_open"]
    net_feats = [{"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": [rnd([c[:2] for c in l]) for l in n["lines"]]},
                  "properties": {"cls": n["cls"], "name": n["name"], "detail": n["detail"]}} for n in sorted(network, key=lambda n: order.index(n["cls"]))]
    dump("network.geojson", {"type": "FeatureCollection", "features": net_feats})
    dump("neighborhoods.geojson", {"type": "FeatureCollection", "features": hoods})
    dump("crashes.geojson", {"type": "FeatureCollection", "features": crashes})
    dump("points.geojson", {"type": "FeatureCollection", "features": points})
    dump("calm.geojson", {"type": "FeatureCollection", "features": calm})
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "labels"}, indent=1))


if __name__ == "__main__":
    build()
