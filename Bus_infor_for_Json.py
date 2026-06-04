import requests
import xml.etree.ElementTree as ET
import json
import time

from config import API_KEY, CITY_CODE  # 설정 파일에서 불러오기

# 1. 모든 노선 번호와 ID를 동적으로 가져오는 함수
def get_all_route_ids():
    url = f"http://apis.data.go.kr/1613000/BusRouteInfoInqireService/getRouteNoList?serviceKey={API_KEY}&cityCode={CITY_CODE}&numOfRows=500&_type=xml"
    routes = {}
    res = requests.get(url)
    root = ET.fromstring(res.content)
    for item in root.findall('.//item'):
        r_no = item.find('routeno').text
        r_id = item.find('routeid').text
        if r_no not in routes: routes[r_no] = []
        routes[r_no].append(r_id)
    return routes

# 2. 상세 정류소 정보를 모두 긁어오는 함수 (URL 변경 반영)
def get_stations(route_id):
    # 상세 정류소 목록 API로 변경
    url = f"http://apis.data.go.kr/1613000/BusRouteInfoInqireService/getRouteAcctoThrghSttnList?serviceKey={API_KEY}&cityCode={CITY_CODE}&routeId={route_id}&numOfRows=200&_type=xml"
    stations = []
    try:
        res = requests.get(url, timeout=5)
        root = ET.fromstring(res.content)
        for item in root.findall('.//item'):
            # 선생님이 원하시는 모든 상세 정보를 리스트에 추가
            stations.append({
                "nodeord": item.find('nodeord').text,     # 순번
                "nodenm": item.find('nodenm').text,       # 이름
                "nodeid": item.find('nodeid').text,       # ID
                "nodeno": item.find('nodeno').text,       # 정류소 번호
                "gpslati": item.find('gpslati').text,     # 위도
                "gpslong": item.find('gpslong').text      # 경도
            })
    except Exception as e:
        print(f"Error on {route_id}: {e}")
    return stations

# 메인 실행
print("진주시 전체 버스 상세 데이터를 수집합니다...")
final_data = {}
all_routes = get_all_route_ids()

for bus_no, r_ids in all_routes.items():
    print(f"[{bus_no}번 버스] 처리 중...")
    final_data[bus_no] = {}
    for r_id in r_ids:
        final_data[bus_no][r_id] = get_stations(r_id)
        time.sleep(0.2) # API 과부하 방지

# JSON 저장
with open('bus_data.json', 'w', encoding='utf-8') as f:
    json.dump(final_data, f, ensure_ascii=False, indent=2)

print("성공! 'bus_data.json'에 상세 정류장 정보가 업데이트되었습니다.")