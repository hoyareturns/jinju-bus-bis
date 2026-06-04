import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import math
import aiohttp
import asyncio

async def fetch_bus_location(session, bus_no, route_id, api_key, city_code):
    """단일 버스 노선의 실시간 위치를 비동기로 가져옵니다."""
    url = f"http://apis.data.go.kr/1613000/BusLcInfoInqireService/getRouteAcctoBusLcList?serviceKey={api_key}&cityCode={city_code}&routeId={route_id}&numOfRows=50&_type=xml"
    try:
        # 타임아웃 3초 설정
        async with session.get(url, timeout=3.0) as response:
            content = await response.read()
            root = ET.fromstring(content)
            items = root.findall('.//item')
            buses = []
            
            kst_now = datetime.now() + timedelta(hours=9)
            time_str = kst_now.strftime("%H:%M:%S")
            
            for item in items:
                node_nm = item.find('nodenm')
                node_ord = item.find('nodeord')
                if node_nm is not None and node_ord is not None:
                    buses.append({
                        "curr": node_nm.text,
                        "ord": int(node_ord.text),
                        "last_time": time_str
                    })
                    
            if not buses:
                return bus_no, [], "운행종료" # 데이터가 비어있으면 운행종료
            return bus_no, buses, "정상"
            
    except asyncio.TimeoutError:
        return bus_no, [], "타임아웃"
    except Exception as e:
        return bus_no, [], f"오류 발생"

async def get_all_bus_locations(targets, api_key, city_code):
    """여러 노선의 위치 데이터를 병렬(비동기)로 가져옵니다."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_bus_location(session, b_no, r_id, api_key, city_code) for b_no, r_id in targets]
        results = await asyncio.gather(*tasks)
        return results

def get_arrival_info(node_id, bus_no, api_key, city_code):
    """특정 정류장의 버스 도착 예정 시간을 가져옵니다."""
    url = f"http://apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList?serviceKey={api_key}&cityCode={city_code}&nodeId={node_id}&_type=xml"
    try:
        res = requests.get(url, timeout=3.0)
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
    return buf.getvalue()

def get_bearing(lat1, lon1, lat2, lon2):
    """두 좌표 간의 방위각을 계산합니다."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dLon = lon2 - lon1
    x = math.sin(dLon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dLon))
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360
    return compass_bearing