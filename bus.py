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

# --- 비동기 데이터 호출 캐싱 (30초 제한으로 트래픽 방어) ---
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
st.sidebar.image(get_qr_image(current_qr_url))
st.sidebar.markdown("---")

target_input = st.sidebar.text_input("버스번호 (쉼표 구분):", value=default_buses)

search_term = st.sidebar.text_input("정류장 검색어 입력:")
all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
filtered_nodes = [n for n in all_nodes if search_term in n] if search_term else all_nodes

options = ["선택 안함"] + filtered_nodes
ref_index = options.index(default_ref) if default_ref in options else 0
ref_name = st.sidebar.selectbox("목표 정류장 선택:", options, index=ref_index)

mode = st.sidebar.radio("보기 모드:", ["버스 위치 추적", "경유 버스 목록", "노선 순서 보기"])

st.query_params["buses"] = target_input
st.query_params["ref"] = ref_name

target_buses = [b.strip() for b in target_input.split(",") if b.strip()]

# --- 메인 화면 영역 ---
if st.button("새로고침"):
    fetch_locations_cached.clear() # 캐시 초기화
    st.rerun()

st.markdown("---")

if mode == "버스 위치 추적":
    with st.spinner("최신 위치 정보를 가져오는 중..."):
        m = folium.Map(location=[35.1800, 128.1076], zoom_start=12, tiles="CartoDB positron")
        
        # 목표 지점 (빨간 깃발)
        target_node_id_for_api = None
        if ref_name != "선택 안함":
            ref_node_data = next((s for bus in bus_db.values() for r in bus.values() for s in r if s['nodenm'] == ref_name), None)
            
            if ref_node_data:
                lat, lon = float(ref_node_data['gpslati']), float(ref_node_data['gpslong'])
                target_node_id_for_api = ref_node_data.get('nodeid', ref_node_data.get('nodeId'))
                
                folium.Marker(
                    location=[lat, lon],
                    popup=ref_name,
                    icon=folium.Icon(color='red', icon='flag', prefix='fa')
                ).add_to(m)
                
                html_dest = f"""
                <div style="position: relative; width: 200px; text-align: center; left: -100px; top: 10px;">
                    <div style="background-color: white; border: 2px solid #d32f2f; border-radius: 5px; padding: 3px 6px; display: inline-block; font-size: 12px; font-weight: bold; color: #d32f2f; box-shadow: 1px 1px 4px rgba(0,0,0,0.4);">
                        {ref_name}
                    </div>
                </div>
                """
                folium.Marker(
                    location=[lat, lon],
                    icon=folium.DivIcon(html=html_dest)
                ).add_to(m)

        # --- 데이터 비동기 병렬 호출 ---
        targets = []
        for bus_no in target_buses:
            if bus_no in bus_db:
                route_id = list(bus_db[bus_no].keys())[0]
                targets.append((bus_no, route_id))

        bus_results_raw = fetch_locations_cached(targets, API_KEY, CITY_CODE)
        
        bus_results = {}
        seen_coords = {} # 마커 겹침 방지를 위한 딕셔너리

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
                        lat = float(curr_node['gpslati'])
                        lon = float(curr_node['gpslong'])
                        color = get_color_by_bus(bus_no)
                        
                        bearing = 0
                        if next_node_data:
                            n_lat = float(next_node_data['gpslati'])
                            n_lon = float(next_node_data['gpslong'])
                            bearing = get_bearing(lat, lon, n_lat, n_lon)
                            
                        # 마커 겹침(Overlapping) 방지 로직 (UI를 해치지 않게 내부 좌표만 미세조정)
                        coord_key = f"{lat:.4f}_{lon:.4f}"
                        if coord_key in seen_coords:
                            offset_count = seen_coords[coord_key]
                            lat += (0.00025 * offset_count)
                            lon -= (0.00025 * offset_count)
                            seen_coords[coord_key] += 1
                        else:
                            seen_coords[coord_key] = 1
                        
                        # 사용자님이 제공한 오리지널 UI 마커 그대로 사용
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
                    
        st_folium(m, width="100%", height=400, returned_objects=[])
        st.markdown("---")

        # --- 하단 텍스트 정보 표출 ---
        for bus_no in target_buses:
            if bus_no in bus_results:
                buses_active, active_nodes = bus_results[bus_no]
                
                # 여러 대의 버스 정보 모두 표시
                for idx, bus_status in enumerate(buses_active):
                    curr_ord = bus_status['ord']
                    next_node_data = next((n for n in active_nodes if int(n['nodeord']) == curr_ord + 1), None)
                    next_node_name = next_node_data['nodenm'] if next_node_data else "운행종료"
                    
                    # 2대 이상일 경우 번호 뒤에 (1), (2) 표시
                    title_suffix = f" ({idx+1}호차)" if len(buses_active) > 1 else ""
                    st.write(f"**[{bus_no}번]{title_suffix}**")
                    st.write(f"현재 : {bus_status['curr']}")
                    st.write(f"다음 : {next_node_name}")
                    
                    eta_displayed = False
                    
                    # 도착 정보 (가장 먼저 오는 1호차에 대해서만 API 시도)
                    if idx == 0 and ref_name != "선택 안함" and target_node_id_for_api:
                        eta_text = get_arrival_info(target_node_id_for_api, bus_no, API_KEY, CITY_CODE)
                        if eta_text:
                            st.write(f"목표까지 : {eta_text} [{ref_name}]")
                            eta_displayed = True
                    
                    if not eta_displayed:
                        info = get_target_info(active_nodes, curr_ord, ref_name, bus_db)
                        if info: st.write(info)
                        
                    st.caption(f"확인 시간 : {bus_status['last_time']}")
                    st.markdown("---")
            else:
                # 통신오류 또는 운행종료
                err_msg = next((res[2] for res in bus_results_raw if res[0] == bus_no), "현재 정보 확인 불가")
                st.write(f"[{bus_no}번] {err_msg}")
                st.markdown("---")

elif mode == "경유 버스 목록":
    if ref_name != "선택 안함":
        buses = find_buses_at_node(bus_db, ref_name)
        st.write(f"[{ref_name}] 경유 버스: {', '.join(buses)}")

elif mode == "노선 순서 보기":
    for bus_no in target_buses:
        if bus_no in bus_db:
            nodes = list(bus_db[bus_no].values())[0]
            sorted_nodes = get_sorted_route(nodes)
            with st.expander(f"{bus_no}번 전체 노선 보기"):
                for n in sorted_nodes:
                    st.write(f"{n['nodeord']}. {n['nodenm']}")