import streamlit as st
import json
import urllib.parse
import folium
import asyncio
from streamlit_folium import st_folium
from bus_utils import get_all_bus_locations, get_qr_image, get_bearing, get_arrival_info
from data_logic import find_buses_at_node, get_sorted_route, get_target_info, get_color_by_bus

API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]
BASE_URL = "https://jinju-bus-bis-bpesd99kxyupdbxgsuwvzt.streamlit.app" 

st.set_page_config(page_title="금산버스", layout="centered")

@st.cache_data
def load_bus_data():
    with open('bus_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

bus_db = load_bus_data()

# 일일 트래픽 초과 방지 및 로딩 속도 개선을 위한 30초 캐싱
@st.cache_data(ttl=30)
def fetch_locations_cached(targets, api_key, city_code):
    return asyncio.run(get_all_bus_locations(targets, api_key, city_code))

query_params = st.query_params
default_buses = query_params.get("buses", "10, 160, 360, 362, 363")
default_ref = query_params.get("ref", "금산우체국/금산푸르지오2단지")

# --- 사이드바 설정 영역 ---
st.sidebar.title("금산버스 설정")
st.sidebar.write("휴대폰 접속 QR")
current_qr_url = f"{BASE_URL}?buses={urllib.parse.quote(default_buses)}&ref={urllib.parse.quote(default_ref)}"
qr_bytes = get_qr_image(current_qr_url)
st.sidebar.image(qr_bytes, caption="현재 설정으로 접속")

input_buses = st.sidebar.text_input("조회할 버스 번호 (쉼표로 구분)", value=default_buses)
target_buses = [b.strip() for b in input_buses.split(',') if b.strip()]

all_nodes = set()
for b in target_buses:
    if b in bus_db:
        for route in bus_db[b].values():
            for node in route:
                all_nodes.add(node['nodenm'])
all_nodes_sorted = ["선택 안함"] + sorted(list(all_nodes))

ref_idx = all_nodes_sorted.index(default_ref) if default_ref in all_nodes_sorted else 0
ref_name = st.sidebar.selectbox("목표 정류장 선택", all_nodes_sorted, index=ref_idx)

mode = st.sidebar.radio("모드 선택", ["지도/상태 보기", "경유 버스 목록", "노선 상세 정보"])

# --- 메인 화면 ---
st.title("🚌 금산 버스 실시간 알리미")
st.caption("※ 공공데이터 API 특성상 실제 위치보다 약 30초~1분 지연될 수 있습니다.")

if mode == "지도/상태 보기":
    map_center = [35.18, 128.10] # 진주 기본 좌표 
    m = folium.Map(location=map_center, zoom_start=12)
    
    # 비동기로 모든 버스 위치 한 번에 조회
    targets = []
    for bus_no in target_buses:
        if bus_no in bus_db:
            route_id = list(bus_db[bus_no].keys())[0]
            targets.append((bus_no, route_id))
            
    with st.spinner("실시간 버스 정보를 가져오는 중..."):
        bus_results = fetch_locations_cached(targets, API_KEY, CITY_CODE)
    
    st.markdown("### 🚦 현재 버스 운행 상태")
    
    for result in bus_results:
        bus_no, buses_active, status_msg = result
        route_id = list(bus_db[bus_no].keys())[0]
        active_nodes = get_sorted_route(bus_db[bus_no][route_id])
        
        # 목표 정류장 node_id 찾기
        target_node_id_for_api = None
        if ref_name != "선택 안함":
            target_node = next((n for n in active_nodes if n['nodenm'] == ref_name), None)
            if target_node:
                target_node_id_for_api = target_node.get('nodeid')

        # 1. 예외 상태 처리 (운행종료, 타임아웃, 통신오류)
        if status_msg != "정상":
            st.error(f"[{bus_no}번] {status_msg}")
            st.markdown("---")
            continue
            
        # 2. 정상 운행 중인 버스 리스트 렌더링
        for idx, bus in enumerate(buses_active):
            curr_ord = bus['ord']
            
            # 방향성에 따른 상태 텍스트, 색상 판별
            info_text, marker_color, direction_icon = get_target_info(active_nodes, curr_ord, ref_name)
            
            # Streamlit 텍스트 출력 (다가옴은 🔴, 멀어짐은 ⚪)
            status_icon = "🔴" if marker_color == "red" else "⚪" if marker_color == "gray" else "🔵"
            st.write(f"**[{bus_no}번]** - {bus['curr']} 통과 {status_icon}")
            
            eta_displayed = False
            # API를 통한 도착 예정 시간 우선 시도 (가장 첫 번째 버스에 대해서만)
            if idx == 0 and ref_name != "선택 안함" and target_node_id_for_api and marker_color == "red":
                eta_text = get_arrival_info(target_node_id_for_api, bus_no, API_KEY, CITY_CODE)
                if eta_text:
                    st.write(f"목표까지 : {eta_text} [{ref_name}]")
                    eta_displayed = True
                    
            # API 실패 또는 멀어지는 버스일 경우 정거장 계산 표시
            if not eta_displayed and info_text:
                st.write(info_text)
                
            st.caption(f"확인 시간 : {bus['last_time']}")
            
            # Folium 지도에 마커 추가
            curr_node = next((n for n in active_nodes if n['nodenm'] == bus['curr']), None)
            if curr_node:
                lat, lon = float(curr_node['gpslati']), float(curr_node['gpslong'])
                
                # 다음 정류장 방위각 계산
                next_node = next((n for n in active_nodes if int(n['nodeord']) == curr_ord + 1), None)
                bearing = 0
                if next_node:
                    n_lat, n_lon = float(next_node['gpslati']), float(next_node['gpslong'])
                    bearing = get_bearing(lat, lon, n_lat, n_lon)
                
                html = f"""
                <div style="background-color: white; border: 2px solid {marker_color}; border-radius: 5px; padding: 2px; text-align: center; white-space: nowrap; transform: rotate({bearing}deg); opacity: {'1.0' if marker_color == 'red' else '0.6'};">
                    <div style="font-size: 14px; transform: rotate(-{bearing}deg);">🚌</div>
                </div>
                <div style="font-size: 12px; font-weight: bold; color: {marker_color}; text-shadow: 1px 1px white;">{bus_no}{direction_icon}</div>
                """
                folium.Marker(
                    location=[lat, lon],
                    icon=folium.DivIcon(html=html),
                    tooltip=f"{bus_no}번 ({bus['curr']})"
                ).add_to(m)
                
        st.markdown("---")

    # 지도 렌더링 (모바일 터치 이슈 완화를 위해 use_container_width 적용)
    st_folium(m, height=400, use_container_width=True, returned_objects=[])

elif mode == "경유 버스 목록":
    if ref_name != "선택 안함":
        buses = find_buses_at_node(bus_db, ref_name)
        st.write(f"[{ref_name}] 경유 버스: {', '.join(buses)}")

elif mode == "노선 상세 정보":
    selected_bus = st.selectbox("버스 번호 선택", target_buses)
    if selected_bus in bus_db:
        route_id = list(bus_db[selected_bus].keys())[0]
        nodes = get_sorted_route(bus_db[selected_bus][route_id])
        st.write(f"### {selected_bus}번 노선")
        for n in nodes:
            st.write(f"{n['nodeord']}. {n['nodenm']}")