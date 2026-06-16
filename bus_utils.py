from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import BytesIO
import math
import time
import xml.etree.ElementTree as ET

import qrcode
import requests


BUS_LOCATION_URL = "http://apis.data.go.kr/1613000/BusLcInfoInqireService/getRouteAcctoBusLcList"
MAX_WORKERS = 8


def _text(parent, name, default=""):
    node = parent.find(name)
    return node.text.strip() if node is not None and node.text else default


def _fetch_bus_location(bus_no, route_id, api_key, city_code):
    url = f"{BUS_LOCATION_URL}?serviceKey={api_key}"
    params = {
        "cityCode": city_code,
        "routeId": route_id,
        "numOfRows": 50,
        "_type": "xml",
    }
    last_error_msg = "통신 지연"

    for attempt in range(3):
        try:
            res = requests.get(url, params=params, timeout=4.0)
            res.raise_for_status()
            root = ET.fromstring(res.content)

            header = root.find(".//header")
            if header is None:
                return bus_no, [], "응답 형식 오류"

            result_code = _text(header, "resultCode")
            result_msg = _text(header, "resultMsg", "API 오류")
            if result_code != "00":
                last_error_msg = f"API 오류({result_code}: {result_msg})"
                continue

            time_str = datetime.now().strftime("%H:%M:%S")
            buses = []
            for item in root.findall(".//item"):
                node_name = _text(item, "nodenm")
                node_ord = _text(item, "nodeord")
                if not node_name or not node_ord:
                    continue
                try:
                    buses.append({"curr": node_name, "ord": int(node_ord), "last_time": time_str})
                except ValueError:
                    continue

            if not buses:
                return bus_no, [], "운행 종료 또는 차량 없음"
            return bus_no, buses, "정상"
        except requests.Timeout:
            last_error_msg = "응답 시간 초과"
        except requests.RequestException:
            last_error_msg = "통신 오류"
        except ET.ParseError:
            last_error_msg = "XML 파싱 오류"

        if attempt < 2:
            time.sleep(0.2 * (attempt + 1))

    return bus_no, [], last_error_msg


def get_all_bus_locations_sync(targets, api_key, city_code):
    """Fetch bus locations concurrently while preserving the requested bus order."""
    if not targets:
        return []

    results_by_bus = {}
    max_workers = min(MAX_WORKERS, len(targets))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_fetch_bus_location, bus_no, route_id, api_key, city_code)
            for bus_no, route_id in targets
        ]
        for future in as_completed(futures):
            bus_no, buses, status = future.result()
            results_by_bus[bus_no] = (bus_no, buses, status)

    return [results_by_bus.get(bus_no, (bus_no, [], "정보 없음")) for bus_no, _ in targets]


def get_qr_image(url):
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf)
    return buf.getvalue()


def get_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (
        math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    )
    initial_bearing = math.atan2(x, y)
    return (math.degrees(initial_bearing) + 360) % 360
