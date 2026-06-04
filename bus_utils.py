import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import qrcode
from io import BytesIO

def get_bus_location(bus_no, route_id, api_key, city_code):
    """실시간 버스 위치 정보를 API에서 가져옵니다."""
    url = f"http://apis.data.go.kr/1613000/BusLcInfoInqireService/getRouteAcctoBusLcList?serviceKey={api_key}&cityCode={city_code}&routeId={route_id}&numOfRows=10&_type=xml"
    try:
        res = requests.get(url, timeout=3)
        root = ET.fromstring(res.content)
        item = root.find('.//item')
        if item is not None:
            # 한국 시간 보정 (UTC + 9)
            kst_now = datetime.now() + timedelta(hours=9)
            return {
                "curr": item.find('nodenm').text,
                "ord": int(item.find('nodeord').text),
                "last_time": kst_now.strftime("%H시 %M분")
            }
    except:
        pass
    return None

def get_qr_image(url):
    """주어진 URL로 QR 코드 이미지를 생성합니다."""
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf)
    return buf