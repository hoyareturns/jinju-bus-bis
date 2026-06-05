import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import math
import time

def get_all_bus_locations_sync(targets, api_key, city_code):
    """안정적인 통신을 위해 순차적으로 호출하며, 실패 시 최대 3번 재시도합니다."""
    results = []
    session = requests.Session() # 세션을 유지하여 통신 안정성 확보
    
    for bus_no, route_id in targets:
        url = f"http://apis.data.go.kr/1613000/BusLcInfoInqireService/getRouteAcctoBusLcList?serviceKey={api_key}&cityCode={city_code}&routeId={route_id}&numOfRows=50&_type=xml"
        
        success = False
        for attempt in range(3): # 에러 방지를 위한 3회 재시도 루프
            try:
                # 타임아웃을 5초로 넉넉하게 주어 지연에 대비
                res = session.get(url, timeout=5.0)
                if res.status_code == 200:
                    root = ET.fromstring(res.content)
                    items = root.findall('.//item') # 모든 버스를 가져옴
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
                        results.append((bus_no, [], "운행종료/정보없음"))
                    else:
                        results.append((bus_no, buses, "정상"))
                    success = True
                    break # 성공 시 루프 탈출
            except Exception as e:
                time.sleep(0.5) # 실패 시 0.5초 대기 후 다시 시도
        
        if not success:
            results.append((bus_no, [], "통신오류"))
            
    return results

def get_arrival_info(node_id, bus_no, api_key, city_code):
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
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dLon = lon2 - lon1
    x = math.sin(dLon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dLon))
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360
    return compass_bearing