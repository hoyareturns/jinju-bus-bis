import streamlit as st
import json
import urllib.parse
import folium
import asyncio
from streamlit_folium import st_folium
from bus_utils import get_all_bus_locations, get_qr_image, get_arrival_info, get_bearing
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

@st.cache_data(ttl=30)
def fetch_locations_cached(targets, api_key, city_code):
    return asyncio.run(get_all_bus_locations(targets, api_key, city_code))

query_params = st.query_params
default_buses = query_params.get("buses", "10, 160, 360, 362, 363")
default_ref = query_params.get("ref", "금산우체국/금산푸르지오2단지")

# --- 1. 사이드바 ---
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

search_kw = st.sidebar.text_input("목표 정류장 검색", "")
filtered_nodes = [n for n in all_nodes_sorted if search_kw in n] if search_kw else all_nodes_sorted

ref_idx = filtered_nodes.index(default_ref) if default_ref in filtered_nodes else 0
ref_name = st.sidebar.selectbox("목표 정류장 선택", filtered_nodes, index=ref_idx)

if ref_name != "선택 안함":
    passing_buses = find_buses_at_node(bus_db, ref_name)
    st.sidebar.info(f"선택 정류장 경유 버스:\n{', '.join(passing_buses)}")


# --- 2. 최상단 컨트롤 (새로고침) ---
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("새로고침"):
        fetch_locations_cached.clear()


# --- 3. 데이터 처리 및 지도 생성 준비 ---
map_center = [35.18, 128.10]
zoom_level = 12

found_target = False
target_lat, target_lon = None, None

if ref_name != "선택 안함":
    for b in target_buses:
        if b in bus_db:
            for route in bus_db[b].values():
                for node in route:
                    if node['nodenm'] == ref_name:
                        target_lat, target_lon = float(node['gpslati']), float(node['gpslong'])
                        map_center = [target_lat, target_lon]
                        found_target = True
                        break
                if found_target: break
        if found_target: break

# 도로 위주의 깔끔한 테마로 원복
m = folium.Map(location=map_center, zoom_start=zoom_level, tiles="CartoDB positron")

if found_target:
    folium.CircleMarker(
        location=[target_lat, target_lon],
        radius=12,
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

# API 호출
with st.spinner("불러오는 중..."):
    bus_results = fetch_locations_cached(targets, API_KEY, CITY_CODE)

seen_coords = {}
details_html = ""
eta_messages = []

# 결과 파싱 (화면에 그리지 않고 HTML 문자열로 먼저 조립)
for result in bus_results:
    bus_no, buses_active, status_msg = result
    
    # 상태 예외 처리
    if status_msg == "운행종료":
        details_html += f"<div style='margin-bottom:10px;'><b style='color:#1f77b4;'>[{bus_no}번]</b> 현재 운행 중인 버스가 없습니다. (운행 종료)</div>"
        continue
    elif status_msg != "정상":
        details_html += f"<div style='margin-bottom:10px;'><b style='color:#d62728;'>[{bus_no}번]</b> 데이터를 불러오지 못했습니다. ({status_msg})</div>"
        continue
        
    route_id = list(bus_db[bus_no].keys())[0]
    active_nodes = get_sorted_route(bus_db[bus_no][route_id])
    
    if buses_active:
        details_html += f"<h4 style='color:#333; border-bottom:1px solid #ddd; padding-bottom:5px; margin-top:20px;'>[{bus_no}번] 현재 {len(buses_active)}대 운행 중</h4>"
    
    # 도착 예정 시간(ETA) 확보
    if buses_active and ref_name != "선택 안함":
        first_bus_ord = buses_active[0]['ord']
        _, m_color = get_target_info(active_nodes, first_bus_ord, ref_name)
        if m_color == "#d62728": 
            target_node = next((n for n in active_nodes if n['nodenm'] == ref_name), None)
            if target_node:
                eta_text = get_arrival_info(target_node.get('nodeid'), bus_no, API_KEY, CITY_CODE)
                if eta_text:
                    eta_messages.append(f"[{bus_no}번] {eta_text}")

    # 마커 생성 및 가로 노선도 조립
    for idx, bus in enumerate(buses_active):
        curr_ord = bus['ord']
        info_text, marker_color = get_target_info(active_nodes, curr_ord, ref_name)
        
        curr_node = next((n for n in active_nodes if n['nodenm'] == bus['curr']), None)
        lat, lon = 0, 0
        if curr_node:
            lat, lon = float(curr_node['gpslati']), float(curr_node['gpslong'])
            
            next_node = next((n for n in active_nodes if int(n['nodeord']) == curr_ord + 1), None)
            bearing = 0
            if next_node:
                n_lat, n_lon = float(next_node['gpslati']), float(next_node['gpslong'])
                bearing = get_bearing(lat, lon, n_lat, n_lon)
            
            coord_key = f"{lat:.4f}_{lon:.4f}"
            if coord_key in seen_coords:
                offset_count = seen_coords[coord_key]
                lat += (0.00025 * offset_count)
                lon -= (0.00025 * offset_count)
                seen_coords[coord_key] += 1
            else:
                seen_coords[coord_key] = 1
            
            # 말풍선 글자 길이에 맞게 자동 조정 (display: inline-block)
            html = f"""
            <div style="
                background-color: {marker_color}; 
                color: white; 
                padding: 6px 12px; 
                border-radius: 8px; 
                font-weight: bold; 
                font-size: 15px;
                white-space: nowrap;
                display: inline-block;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.5);
                text-align: center;
                border: 2px solid white;
                position: relative;
            ">
                {bus_no}번<br><span style="font-size: 13px; font-weight: normal;">{bus['curr']}</span>
                <div style="
                    position: absolute; 
                    top: -12px; right: -12px; 
                    background: white; 
                    color: {marker_color}; 
                    border-radius: 50%; 
                    width: 24px; height: 24px; 
                    line-height: 24px; 
                    text-align: center; 
                    font-size: 15px;
                    transform: rotate({bearing}deg);
                    box-shadow: 1px 1px 3px rgba(0,0,0,0.3);
                ">↑</div>
            </div>
            """
            
            folium.Marker(
                location=[lat, lon],
                icon=folium.DivIcon(html=html, icon_anchor=(40, 30)),
                tooltip=f"{bus_no}번: {bus['curr']}"
            ).add_to(m)

        # 가로 노선도 (스마트 자르기) 조립
        details_html += f"<div style='margin-bottom:15px;'>"
        details_html += f"<b>{bus['curr']} 통과</b> <span style='font-size:0.8em;color:gray;'>({bus['last_time']} 기준)</span><br>"
        
        route_html = "<div style='overflow-x: auto; white-space: nowrap; padding: 12px; background-color: #f8f9fa; border-radius: 8px; font-size: 13px; border: 1px solid #e9ecef; margin-top:5px;'>"
        
        curr_idx = 0
        for i, n in enumerate(active_nodes):
            if int(n['nodeord']) == curr_ord:
                curr_idx = i
                break
                
        start_idx = max(0, curr_idx - 3)
        end_idx = min(len(active_nodes), curr_idx + 6)
        
        path_spans = []
        if start_idx > 0:
            path_spans.append("<span style='color:#adb5bd;'>...</span>")
            
        for n in active_nodes[start_idx:end_idx]:
            n_ord = int(n['nodeord'])
            n_name = n['nodenm']
            
            if n_ord < curr_ord:
                path_spans.append(f"<span style='color:#adb5bd;'>{n_name}</span>")
            elif n_ord == curr_ord:
                path_spans.append(f"<span style='color:#d62728; font-weight:bold; font-size: 15px;'>📍{n_name}</span>")
            else:
                path_spans.append(f"<span style='color:#212529;'>{n_name}</span>")
                
        if end_idx < len(active_nodes):
            path_spans.append("<span style='color:#212529;'>...</span>")
                
        route_html += " &gt; ".join(path_spans)
        route_html += "</div></div>"
        
        details_html += route_html


# --- 4. 화면 최상단에 지도 출력 ---
# 지도를 새로고침 버튼 바로 아래에 렌더링 (밀림 방지)
st_folium(m, height=450, use_container_width=True, returned_objects=[])


# --- 5. 지도 하단에 상세 정보 출력 (기본 펼침 설정) ---
# expanded=True 속성으로 접속하자마자 상세 정보가 보이도록 설정
with st.expander("상세 운행 노선 및 도착 예정 시간", expanded=True):
    
    if eta_messages:
        st.markdown("**🎯 목표 정류장 실시간 도착 정보**")
        for msg in eta_messages:
            st.success(msg)
        st.markdown("---")
        
    if details_html:
        st.markdown(details_html, unsafe_allow_html=True)
    else:
        st.info("조회된 운행 정보가 없습니다.")