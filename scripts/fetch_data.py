"""Download the raw inputs for Detroit Wheels from the City of Detroit Open Data Portal into data/raw/."""
import json
import urllib.parse
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
B = "https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services"
CRASH_LAYERS = {2020: 9, 2021: 10, 2022: 11, 2023: 12, 2024: 13}


def get(url, **params):
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=120) as r:
        return json.load(r)


def features(service, layer=0, fields="*", where="1=1", simplify=0):
    feats, offset = [], 0
    while True:
        params = dict(where=where, outFields=fields, outSR=4326, f="geojson", resultOffset=offset, resultRecordCount=1000)
        if simplify:
            params["maxAllowableOffset"] = simplify
        d = get(f"{B}/{service}/FeatureServer/{layer}/query", **params)
        batch = d["features"]
        feats += batch
        if not batch or not d.get("properties", {}).get("exceededTransferLimit"):
            return feats
        offset += len(batch)


def save(name, feats):
    (RAW / f"{name}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(name, len(feats))


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    save("bike_lanes", features("bike_routes_and_facilities", fields="route_name,on_road_type,protected_bike_lane_type,trail_type,jurisdiction"))
    save("greenways", features("gsd_city_of_detroit_greenways", fields="greenway_name,tier,typology"))
    save("jlg", features("Joe_Louis_Greenway_Routes", fields="ROUTE_SEGMENT_NAME,PHASE,PHASE_DESCRIPTION,TYPOLOGY"))
    save("mogo", features("mogo_stations", fields="station_name,capacity"))
    save("repair", features("Bicycle_Repair_Stations", fields="STATION_NAME,STATUS,NEIGHBORHOOD"))
    save("slow_streets", features("detroit_slow_streets", fields="street_name,neighborhood", simplify=0.00005))
    save("safe_streets", features("safe_streets_for_detroit_corridors", fields="street_name,corridor_extents,scope_type,status,completion_year"))
    crashes = []
    for year, layer in CRASH_LAYERS.items():
        crashes += features("Traffic_Crashes", layer, "crash_date,year,primary_road,intersecting_road,num_fatal_injuries,num_suspected_serious_injuries,most_severe_injury_code",
                            where="is_bicycle_involved='true'")
    save("bike_crashes", crashes)


if __name__ == "__main__":
    main()
