import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import math

def get_bus_location(bus_no, route_id, api_key, city_code):
    url = f"http://apis.data.go.kr/1613000/BusLcInfoInqireService/getRouteAcctoBusLcList?serviceKey={api_key}&cityCode={city_code}&routeId={route_id}&numOfRows=10&_type=xml"
    try:
        # API 통신 지연 방지를 위해 타임아웃 0.8초 설정
        res = requests.get(url, timeout=0.8)
        root = ET.fromstring(res.content)
        item = root.find('.//item')
        if item is not None:
            kst_now = datetime.now() + timedelta(hours=9)
            return {
                "curr": item.find('nodenm').text,
                "ord": int(item.find('nodeord').text),
                "last_time": kst_now.strftime("%H:%M:%S")
            }
    except:
        pass
    return None

def get_arrival_info(node_id, bus_no, api_key, city_code):
    url = f"http://apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList?serviceKey={api_key}&cityCode={city_code}&nodeId={node_id}&_type=xml"
    try:
        res = requests.get(url, timeout=0.8)
        root = ET.fromstring(res.content)
        for item in root.findall('.//item'):
            routeno = item.find('routeno')
            if routeno is not None and str(routeno.text) == str(bus_no):
                arrtime = item.find('arrtime')
                if arrtime is not None:
                    eta_mins = int(arrtime.text) // 60
                    if eta_mins == 0:
                        return "잠시 후 도착 예정"
                    return f"약 {eta_mins}분 후 도착 예정"
    except:
        pass
    return None

def get_qr_image(url):
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf)
    return buf

def get_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    return (initial_bearing + 360) % 360