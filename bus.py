import streamlit as st
import json
import urllib.parse
import folium
import asyncio
from streamlit_folium import st_folium
from bus_utils import get_all_bus_locations, get_qr_image, get_arrival_info
from data_logic import find_buses_at_node, get_sorted_route, get_target_info

API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]
BASE_URL = "https://jinju-bus-bis-bpesd99kxyupdbxgsuwvzt.streamlit.app" 

# 모바일 화면을 꽉 채우기 위한 설정 및 불필요한 기본 여백 제거
st.set_page_config(page_title="금산버스", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_bus_data():
    with open('bus_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

bus_db = load_bus_data()

# 트래픽 초과 방지를 위한 30초 캐싱
@st.cache_data(ttl=30)
def fetch_locations_cached(targets, api_key, city_code):
    return asyncio.run(get_all_bus_locations(targets, api_key, city_code))

query_params = st.query_params
default_buses = query_params.get("buses", "10, 160, 360, 362, 363")
default_ref = query_params.get("ref", "금산우체국/금산푸르지오2단지")

# --- 1. 사이드바 (QR코드로 접속 시 기본적으로 숨겨져 있음) ---
st.sidebar.title("설정")
current_qr_url = f"{BASE_URL}?buses={urllib.parse.quote(default_buses)}&ref={urllib.parse.quote(default_ref)}"
qr_bytes = get_qr_image(current_qr_url)
st.sidebar.image(qr_bytes, caption="현재 설정 접속 QR")

input_buses = st.sidebar.text_input("조회 버스 (쉼표 구분)", value=default_buses)
target_buses = [b.strip() for b in input_buses.split(',') if b.strip()]

all_nodes = set()
for b in target_buses:
    if b in bus_db:
        for route in bus_db[b].values():
            for node in route:
                all_nodes.add(node['nodenm'])
all_nodes_sorted = ["선택 안함"] + sorted(list(all_nodes))
ref_idx = all_nodes_sorted.index(default_ref) if default_ref in all_nodes_sorted else 0
ref_name = st.sidebar.selectbox("목표 정류장", all_nodes_sorted, index=ref_idx)


# --- 2. 최상단 컨트롤 (새로고침 버튼) ---
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("새로고침"):
        fetch_locations_cached.clear()


# --- 3. 지도 렌더링 (가장 중요한 정보) ---
map_center = [35.18, 128.10] # 진주 기본 좌표
zoom_level = 13

# ✨ 추가된 기능: 목표 정류장으로 지도 포커싱
found_target = False
if ref_name != "선택 안함":
    for b in target_buses:
        if b in bus_db:
            for route in bus_db[b].values():
                for node in route:
                    if node['nodenm'] == ref_name:
                        map_center = [float(node['gpslati']), float(node['gpslong'])]
                        zoom_level = 14 # 정류장 위치를 잘 볼 수 있도록 약간 확대
                        found_target = True
                        break
                if found_target: break
        if found_target: break

# 도로 위주로 보이게 타일 설정
m = folium.Map(location=map_center, zoom_start=zoom_level, tiles="CartoDB positron")

# ✨ 추가 디테일: 목표 정류장 위치에 지도 가독성을 해치지 않는 투명한 파란색 원을 표시하여 위치 인지 도움
if ref_name != "선택 안함" and found_target:
    folium.CircleMarker(
        location=map_center,
        radius=8,
        color='#1f77b4',
        fill=True,
        fill_color='#1f77b4',
        fill_opacity=0.3,
        weight=2,
        tooltip=f"목표: {ref_name}"
    ).add_to(m)

targets = []
for bus_no in target_buses:
    if bus_no in bus_db:
        route_id = list(bus_db[bus_no].keys())[0]
        targets.append((bus_no, route_id))

with st.spinner("불러오는 중..."):
    bus_results = fetch_locations_cached(targets, API_KEY, CITY_CODE)

seen_coords = {} # 마커 겹침 방지를 위한 딕셔너리
details_html = "" # 하단 Expander에 표시할 상세 텍스트 수집

for result in bus_results:
    bus_no, buses_active, status_msg = result
    
    if status_msg != "정상":
        details_html += f"<p><b>[{bus_no}번]</b> {status_msg}</p>"
        continue
        
    route_id = list(bus_db[bus_no].keys())[0]
    active_nodes = get_sorted_route(bus_db[bus_no][route_id])
    
    for idx, bus in enumerate(buses_active):
        curr_ord = bus['ord']
        info_text, marker_color = get_target_info(active_nodes, curr_ord, ref_name)
        
        # 상세 텍스트 누적
        details_html += f"<p><b>[{bus_no}번]</b> {bus['curr']} ({info_text if info_text else '운행중'}) - <span style='font-size:0.8em;color:gray;'>{bus['last_time']}</span></p>"
        
        # 지도 마커 그리기
        curr_node = next((n for n in active_nodes if n['nodenm'] == bus['curr']), None)
        if curr_node:
            lat, lon = float(curr_node['gpslati']), float(curr_node['gpslong'])
            
            # 마커 겹침(Overlapping) 방지 로직
            coord_key = f"{lat:.4f}_{lon:.4f}"
            if coord_key in seen_coords:
                offset_count = seen_coords[coord_key]
                # 겹칠 경우 미세하게 좌표 분산
                lat += (0.00025 * offset_count)
                lon -= (0.00025 * offset_count)
                seen_coords[coord_key] += 1
            else:
                seen_coords[coord_key] = 1
            
            # 깔끔한 말풍선 스타일 UI (이모지 없음)
            html = f"""
            <div style="
                background-color: {marker_color}; 
                color: white; 
                padding: 4px 8px; 
                border-radius: 4px; 
                font-weight: bold; 
                font-size: 13px;
                white-space: nowrap;
                box-shadow: 1px 1px 4px rgba(0,0,0,0.4);
                text-align: center;
                border: 1px solid white;
            ">
                {bus_no}번<br><span style="font-size: 11px; font-weight: normal;">{bus['curr']}</span>
            </div>
            """
            
            folium.Marker(
                location=[lat, lon],
                icon=folium.DivIcon(html=html, icon_anchor=(30, 20)),
                tooltip=f"{bus_no}번: {bus['curr']}"
            ).add_to(m)

# 지도 표출 (모바일 스크롤 없애기 위해 높이 최적화)
st_folium(m, height=500, use_container_width=True, returned_objects=[])


# --- 4. 상세 텍스트 정보 (하단 접기 UI) ---
with st.expander("상세 운행 및 도착 예정 시간", expanded=False):
    if details_html:
        st.markdown(details_html, unsafe_allow_html=True)
    else:
        st.write("현재 운행중인 버스가 없습니다.")
        
    st.markdown("---")
    st.markdown("**목표 정류장 실시간 도착 정보**")
    for result in bus_results:
        bus_no, buses_active, status_msg = result
        if status_msg == "정상" and buses_active and ref_name != "선택 안함":
            route_id = list(bus_db[bus_no].keys())[0]
            active_nodes = get_sorted_route(bus_db[bus_no][route_id])
            first_bus_ord = buses_active[0]['ord']
            
            _, m_color = get_target_info(active_nodes, first_bus_ord, ref_name)
            if m_color == "#d62728": # 다가오는 버스에 대해서만 API 호출
                target_node = next((n for n in active_nodes if n['nodenm'] == ref_name), None)
                if target_node:
                    eta_text = get_arrival_info(target_node.get('nodeid'), bus_no, API_KEY, CITY_CODE)
                    if eta_text:
                        st.write(f"[{bus_no}번] {eta_text}")