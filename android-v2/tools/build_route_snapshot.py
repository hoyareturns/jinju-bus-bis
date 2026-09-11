from __future__ import annotations

import argparse
import json
from pathlib import Path

LANDMARK_NAMES = [
    "금산우체국/금산푸르지오2단지",
    "선학사거리/제일여자고등학교",
    "경상대(가좌)",
    "중앙시장(주차장)",
    "경남서부보훈지청",
]


def _stop_payload(node: dict) -> dict:
    return {
        "id": str(node.get("nodeid", "")),
        "ord": int(node["nodeord"]),
        "name": str(node.get("nodenm", "")),
        "lat": float(node["gpslati"]) if node.get("gpslati") not in (None, "") else None,
        "lon": float(node["gpslong"]) if node.get("gpslong") not in (None, "") else None,
    }


def build_snapshot(bus_db: dict, landmark_names: list[str] | None = None) -> dict:
    landmark_names = LANDMARK_NAMES if landmark_names is None else landmark_names
    routes: dict[str, dict[str, list[dict]]] = {}
    landmark_by_name: dict[str, dict] = {}

    for bus_no, variants in bus_db.items():
        compact_variants: dict[str, list[dict]] = {}
        for route_id, nodes in variants.items():
            compact_stops = sorted((_stop_payload(node) for node in nodes), key=lambda stop: stop["ord"])
            compact_variants[str(route_id)] = compact_stops
            for stop in compact_stops:
                if stop["name"] in landmark_names and stop["name"] not in landmark_by_name:
                    landmark_by_name[stop["name"]] = {
                        "name": stop["name"],
                        "lat": stop["lat"],
                        "lon": stop["lon"],
                    }
        routes[str(bus_no)] = compact_variants

    landmarks = [landmark_by_name[name] for name in landmark_names if name in landmark_by_name]
    return {"version": 1, "landmarks": landmarks, "routes": routes}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact Jinju bus route snapshot")
    parser.add_argument("source", nargs="?", default="bus_data.json")
    parser.add_argument("output", nargs="?", default="android/app/src/main/assets/routes_snapshot.json")
    args = parser.parse_args()

    source = Path(args.source)
    output = Path(args.output)
    bus_db = json.loads(source.read_text(encoding="utf-8"))
    snapshot = build_snapshot(bus_db)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
