from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
ROOT_DIR = APP_DIR.parent
DEFAULT_BUSES = "10, 160, 360, 362, 363"
DEFAULT_CENTER = [35.1800, 128.1076]
DEFAULT_NODE_1 = "금산우체국/금산푸르지오2단지"

sys.path.insert(0, str(ROOT_DIR))

from bus_utils import get_all_bus_locations_sync  # noqa: E402
from data_logic import build_bus_index, get_route_id  # noqa: E402


def load_bus_data():
    with (ROOT_DIR / "bus_data.json").open("r", encoding="utf-8") as f:
        return json.load(f)


BUS_DB = load_bus_data()
BUS_INDEX = build_bus_index(BUS_DB)


def get_config_value(name):
    value = os.environ.get(name)
    if value:
        return value

    secrets_path = ROOT_DIR / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return None

    prefix = f"{name} ="
    for raw_line in secrets_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def node_payload(name):
    node = BUS_INDEX["node_lookup"].get(name)
    if not node:
        return None
    return {
        "name": name,
        "lat": float(node["gpslati"]),
        "lon": float(node["gpslong"]),
        "buses": sorted(BUS_INDEX["node_to_buses"].get(name, []), key=str),
    }


def calc_bearing(lat1, lon1, lat2, lon2):
    from bus_utils import get_bearing

    return get_bearing(lat1, lon1, lat2, lon2)


def enrich_location_result(bus_no, buses_active, status_msg):
    route_id = get_route_id(BUS_DB, bus_no)
    route_nodes = BUS_DB.get(bus_no, {}).get(route_id, []) if route_id else []
    nodes_by_ord = {int(n["nodeord"]): n for n in route_nodes}

    enriched = []
    for bus in buses_active:
        curr_ord = bus["ord"]
        curr_node = nodes_by_ord.get(curr_ord)
        next_node = nodes_by_ord.get(curr_ord + 1)
        item = dict(bus)
        if curr_node:
            item["lat"] = float(curr_node["gpslati"])
            item["lon"] = float(curr_node["gpslong"])
        if next_node:
            item["next"] = next_node["nodenm"]
            if curr_node:
                item["bearing"] = calc_bearing(
                    float(curr_node["gpslati"]),
                    float(curr_node["gpslong"]),
                    float(next_node["gpslati"]),
                    float(next_node["gpslong"]),
                )
        else:
            item["next"] = "운행 종료"
            item["bearing"] = 0
        enriched.append(item)

    return {"busNo": bus_no, "status": status_msg, "buses": enriched}


class AppHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        parsed = urlparse(path)
        request_path = parsed.path
        if request_path == "/":
            request_path = "/index.html"
        return str(STATIC_DIR / request_path.lstrip("/"))

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            nodes = [node_payload(name) for name in BUS_INDEX["all_nodes"]]
            self.send_json(
                {
                    "defaultBuses": DEFAULT_BUSES,
                    "defaultCenter": DEFAULT_CENTER,
                    "defaultNode1": DEFAULT_NODE_1,
                    "nodes": [n for n in nodes if n],
                }
            )
            return

        if parsed.path == "/api/locations":
            api_key = get_config_value("API_KEY")
            city_code = get_config_value("CITY_CODE")
            if not api_key or not city_code:
                self.send_json({"error": "API_KEY 또는 CITY_CODE가 설정되지 않았습니다."}, status=500)
                return

            params = parse_qs(parsed.query)
            bus_numbers = [
                b.strip()
                for b in params.get("buses", [DEFAULT_BUSES])[0].split(",")
                if b.strip()
            ]
            targets = []
            missing = []
            for bus_no in bus_numbers:
                route_id = get_route_id(BUS_DB, bus_no)
                if route_id:
                    targets.append((bus_no, route_id))
                else:
                    missing.append({"busNo": bus_no, "status": "노선 정보 없음", "buses": []})

            raw_results = get_all_bus_locations_sync(targets, api_key, city_code) if targets else []
            results = [enrich_location_result(*row) for row in raw_results]
            self.send_json({"results": results + missing})
            return

        if parsed.path.endswith(".webmanifest"):
            mimetypes.add_type("application/manifest+json", ".webmanifest")
        return super().do_GET()


def main():
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    print(f"Mobile app server: http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

