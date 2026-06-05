import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import math
import time

def get_all_bus_locations_sync(targets, api_key, city_code):
    """안정적인 통신을 위해 순차적으로 호출하며, 에러 코드를 확인하고 재시도합니다."""
    results = []
    
    for bus_no, route_id in targets:
        url = f"http://apis.data.go.kr/1613000/BusLcInfoInqireService/getRouteAcctoBusLcList?serviceKey={api_key}&cityCode={city_code}&routeId={route_id}&numOfRows=50&_type=xml"
        
        success = False
        last_error_msg = ""
        
        for attempt in range(3): # 에러 방지를 위한 3회 재시도 루프
            try:
                res = requests.get(url, timeout=5.0)
                if res.status_code == 200:
                    root = ET.fromstring(res.content)
                    
                    # API 자체 에러 코드 확인 (정상 코드는 '00')
                    header = root.find('.//header')
                    if header is not None:
                        result_code = header.find('resultCode').text
                        result_msg = header.find('resultMsg').text
                        
                        if result_code == "00": # 완벽한 정상 응답
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
                                results.append((bus_no, [], "운행종료 (차량없음)"))
                            else:
                                results.append((bus_no, buses, "정상"))
                            success = True
                            break # 성공 시 루프 탈출
                        else:
                            # 00이 아니면 API 제한 에러 (트래픽 초과 등)
                            last_error_msg = f"API 오류({result_code})"
                    else:
                        last_error_msg = "XML 파싱 오류"
            except Exception as e:
                last_error_msg = "통신 지연"
                
            time.sleep(0.5) # 실패 시 0.5초 대기 후 다시 시도
        
        if not success:
            results.append((bus_no, [], last_error_msg))
            
        # ⭐️ 가장 중요한 부분: 다음 버스를 물어보기 전에 0.2초를 무조건 쉬어줍니다.
        # 이렇게 하면 공공데이터 서버가 공격(DDoS)으로 오해하고 차단하는 것을 막을 수 있습니다.
        time.sleep(0.2) 
            
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