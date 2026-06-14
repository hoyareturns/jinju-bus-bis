import streamlit as st
import json
import urllib.parse
import folium
from streamlit_folium import st_folium
from bus_utils import get_all_bus_locations_sync, get_qr_image, get_bearing
from data_logic import find_buses_at_node, get_sorted_route, get_color_by_bus

API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]
BASE_URL = "https://jinju-bus-bis-bpesd99kxyupdbxgsuwvzt.streamlit.app" 

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

# --- 동기식 API 호출 및 30초 캐싱 ---
@st.cache_data(ttl=30)
def fetch_locations_cached(targets, api_key, city_code):
    return get_all_bus_locations_sync(targets, api_key, city_code)

query_params = st.query_params
default_buses = query_params.get("buses", "10, 160, 360, 362, 363")
default_ref = query_params.get("ref", "금산우체국/금산푸르지오2단지")

# --- 1. 사이드바 ---
st.sidebar.title("금산버스 설정")
current_qr_url = f"{BASE_URL}?buses={urllib.parse.quote(default_buses)}&ref={urllib.parse.quote(default_ref)}"
st.sidebar.image(get_qr_image(current_qr_url), caption="접속 QR")
st.sidebar.markdown("---")

target_input = st.sidebar.text_input("버스번호 (쉼표 구분):", value=default_buses)
target_buses = [b.strip() for b in target_input.split(",") if b.strip()]

search_term = st.sidebar.text_input("정류장 검색어 입력:")
all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
filtered_nodes = [n for n in all_nodes if search_term in n] if search_term else all_nodes

options = ["선택 안함"] + filtered_nodes
ref_index = options.index(default_ref) if default_ref in options else 0
ref_name = st.sidebar.selectbox("목표 정류장 선택:", options, index=ref_index)

# --- 2. 최상단 새로고침 ---
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("🔄 새로고침"):
        fetch_locations_cached.clear()

# --- 3. 데이터 로드 및 오리지널 지도 렌더링 ---
map_center = [35.1800, 128.1076]
m = folium.Map(location=map_center, zoom_start=12, tiles="CartoDB positron")

if ref_name != "선택 안함":
    ref_node_data = next((s for bus in bus_db.values() for r in bus.values() for s in r if s['nodenm'] == ref_name), None)
    if ref_node_data:
        lat, lon = float(ref_node_data['gpslati']), float(ref_node_data['gpslong'])
        # 목표 지점 빨간 깃발
        folium.Marker(
            location=[lat, lon],
            icon=folium.Icon(color='red', icon='flag', prefix='fa')
        ).add_to(m)

targets = []
for bus_no in target_buses:
    if bus_no in bus_db:
        route_id = list(bus_db[bus_no].keys())[0]
        targets.append((bus_no, route_id))

with st.spinner("최신 위치 정보를 가져오는 중 (최대 5초 소요)..."):
    bus_results_raw = fetch_locations_cached(targets, API_KEY, CITY_CODE)

bus_results = {}
seen_coords = {} 

for res in bus_results_raw:
    bus_no, buses_active, status_msg = res
    if status_msg == "정상" and buses_active:
        route_id = list(bus_db[bus_no].keys())[0]
        active_nodes = bus_db[bus_no][route_id]
        bus_results[bus_no] = (buses_active, active_nodes)
        
        for bus_status in buses_active:
            curr_ord = bus_status['ord']
            curr_node = next((n for n in active_nodes if int(n['nodeord']) == curr_ord), None)
            next_node_data = next((n for n in active_nodes if int(n['nodeord']) == curr_ord + 1), None)
            
            if curr_node:
                lat, lon = float(curr_node['gpslati']), float(curr_node['gpslong'])
                color = get_color_by_bus(bus_no)
                
                bearing = 0
                if next_node_data:
                    n_lat, n_lon = float(next_node_data['gpslati']), float(next_node_data['gpslong'])
                    bearing = get_bearing(lat, lon, n_lat, n_lon)
                    
                # 마커 겹침 방지 (좌표 미세 조정)
                coord_key = f"{lat:.4f}_{lon:.4f}"
                if coord_key in seen_coords:
                    offset_count = seen_coords[coord_key]
                    lat += (0.00025 * offset_count)
                    lon -= (0.00025 * offset_count)
                    seen_coords[coord_key] += 1
                else:
                    seen_coords[coord_key] = 1
                
                # [오리지널 심플 마커]
                html = f"""
                <div style="position: relative; width: 40px; height: 40px;">
                    <div style="position: absolute; left: 14px; top: 14px; width: 14px; height: 14px; background-color: {color}; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 10;">
                        <div style="transform: rotate({bearing}deg); color: white; font-size: 10px; font-weight: bold; line-height: 1;">&uarr;</div>
                    </div>
                    <div style="position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%); background-color: white; border: 2px solid {color}; border-radius: 6px; padding: 3px 6px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); white-space: nowrap; z-index: 5;">
                        <div style="font-size: 12px; font-weight: bold; color: {color};">{bus_no}</div>
                        <div style="font-size: 10px; color: #333; font-weight: bold;">{bus_status['curr']}</div>
                    </div>
                    <div style="position: absolute; bottom: 24px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid {color}; z-index: 4;"></div>
                </div>
                """
                folium.Marker(
                    location=[lat, lon],
                    icon=folium.DivIcon(html=html, icon_size=(40, 40), icon_anchor=(20, 20))
                ).add_to(m)

# 지도 표출
st_folium(m, height=450, use_container_width=True, returned_objects=[])


# --- 4. 하단 상세 정보 (가로 노선도 전체 표기 및 자동 스크롤) ---
with st.expander("상세 운행 노선", expanded=True):
    for bus_no in target_buses:
        err_msg = next((res[2] for res in bus_results_raw if res[0] == bus_no), None)
        if err_msg and err_msg != "정상":
            st.error(f"[{bus_no}번] {err_msg}")
            st.markdown("---")
            continue
            
        if bus_no in bus_results:
            buses_active, active_nodes = bus_results[bus_no]
            st.markdown(f"<h4 style='color:#333;'>[{bus_no}번] 현재 {len(buses_active)}대 운행 중</h4>", unsafe_allow_html=True)
            
            for idx, bus_status in enumerate(buses_active):
                curr_ord = bus_status['ord']
                next_node_data = next((n for n in active_nodes if int(n['nodeord']) == curr_ord + 1), None)
                next_node_name = next_node_data['nodenm'] if next_node_data else "운행종료"
                
                title_suffix = f" <span style='font-size:14px; color:gray;'>( {idx+1}호차 )</span>" if len(buses_active) > 1 else ""
                st.markdown(f"**{bus_status['curr']} 통과** {title_suffix}", unsafe_allow_html=True)
                st.write(f"▶ 다음 정류장 : {next_node_name}")
                
                # 각 버스별 고유 ID 생성 (스크롤 제어용)
                container_id = f"route-container-{bus_no}-{idx}"
                current_id = f"current-node-{bus_no}-{idx}"
                
                # 가로 스크롤 노선도 조립 (생략 없이 active_nodes 전체 순회)
                path_spans = []
                for n in active_nodes:
                    n_ord = int(n['nodeord'])
                    n_name = n['nodenm']
                    if n_ord < curr_ord:
                        path_spans.append(f"<span style='color:#adb5bd;'>{n_name}</span>")
                    elif n_ord == curr_ord:
                        # 현재 위치 정류소 엘리먼트에 고유 ID 부여
                        path_spans.append(f"<span id='{current_id}' style='color:#d62728; font-weight:bold; font-size: 15px;'>📍{n_name}</span>")
                    else:
                        path_spans.append(f"<span style='color:#212529;'>{n_name}</span>")
                
                # HTML 컨테이너 생성
                route_html = f"""
                <div id="{container_id}" style="overflow-x: auto; white-space: nowrap; padding: 12px; background-color: #f8f9fa; border-radius: 8px; font-size: 13px; border: 1px solid #e9ecef; margin-top:5px; margin-bottom:5px;">
                    {" &gt; ".join(path_spans)}
                </div>
                """
                st.markdown(route_html, unsafe_allow_html=True)
                
                # ✨ 화면이 로드되면 현재 위치(📍) 정류장이 가로 스크롤바의 정중앙에 오도록 계산하는 스크립트
                js_scroll = f"""
                <script>
                    setTimeout(function() {{
                        var container = document.getElementById('{container_id}');
                        var element = document.getElementById('{current_id}');
                        if (container && element) {{
                            // 현재 정류장 위치를 컨테이너 중심 정렬 계산
                            container.scrollLeft = element.offsetLeft - (container.clientWidth / 2) + (element.clientWidth / 2);
                        }}
                    }}, 150);
                </script>
                """
                st.markdown(js_scroll, unsafe_allow_html=True)
                st.write("") # 간격 조절
                
            st.markdown("---")