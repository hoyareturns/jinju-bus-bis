import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import time

def get_bus_location(bus_no, route_id, api_key, city_code, retries=2):
    url = f"http://apis.data.go.kr/1613000/BusLcInfoInqireService/getRouteAcctoBusLcList?serviceKey={api_key}&cityCode={city_code}&routeId={route_id}&numOfRows=10&_type=xml"
    
    # 실패 시 retries 횟수만큼 재시도하는 루프
    for attempt in range(retries + 1):
        try:
            res = requests.get(url, timeout=3)
            root = ET.fromstring(res.content)
            item = root.find('.//item')
            if item is not None:
                kst_now = datetime.now() + timedelta(hours=9)
                return {
                    "curr": item.find('nodenm').text,
                    "ord": int(item.find('nodeord').text),
                    "last_time": kst_now.strftime("%H:%M:%S") # 초 단위 추가
                }
        except:
            pass
        
        # 실패 시 0.5초 대기 후 다시 시도
        if attempt < retries:
            time.sleep(0.5)
            
    return None

def get_qr_image(url):
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf)
    return buf