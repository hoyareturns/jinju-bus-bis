import streamlit as st
import json
import urllib.parse
import folium
from streamlit_folium import st_folium
from concurrent.futures import ThreadPoolExecutor
from bus_utils import get_bus_location, get_qr_image, get_bearing, get_arrival_info
from data_logic import find_buses_at_node, get_sorted_route, get_target_info, get_color_by_bus

# 다른 모듈창에 정의된 공용 변수 호출 (모듈명은 실제 환경에 맞게 수정하세요)
from common_vars import API_KEY, CITY_CODE, BASE_URL

st.set_page_config(page_title="금산버스", layout="centered")

@st.cache_data
def load_bus_data():
    with open('bus_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

bus_db = load_bus_data()

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
                
                # 정류장 마커 크기 및 UI 간소화
                folium.Marker(
                    location=[lat, lon],
                    popup=ref_name,
                    icon=folium.Icon(color='red', icon='flag', prefix='fa', icon_size=(20, 20))
                ).add_to(m)
                
                html_dest = f"""
                <div style="font-size: 10px; font-weight: bold; color: #d32f2f; 
                            background-color: rgba(255, 255, 255, 0.8); 
                            padding: 2px 4px; border-radius: 4px; border: 1px solid #d32f2f;
                            white-space: nowrap; position: relative; left: -50%; top: 10px;">
                    {ref_name}
                </div>
                """
                folium.Marker(
                    location=[lat, lon],
                    icon=folium.DivIcon(html=html_dest)
                ).add_to(m)

        bus_results = {}

        # 멀티스레딩 API 호출
        def fetch_bus_info(bus_no):
            if bus_no not in bus_db: return bus_no, None, None
            for route_id, route_nodes in bus_db[bus_no].items():
                loc_data = get_bus_location(bus_no, route_id, API_KEY, CITY_CODE)
                if loc_data:
                    return bus_no, loc_data, route_nodes
            return bus_no, None, None

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(fetch_bus_info, target_buses))

        for bus_no, status, active_nodes in results:
            bus_results[bus_no] = (status, active_nodes)
            
            if status:
                curr_ord = status['ord']
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
                    
                    # 가독성을 높인 버스 아이콘 레이아웃 적용
                    html = f"""
                    <div style="position: relative; width: 100px; height: 50px;">
                        <div style="position: absolute; display: flex; align-items: center; background-color: white; 
                                    border: 2px solid {color}; border-radius: 8px; padding: 2px 5px; 
                                    box-shadow: 2px 2px 5px rgba(0,0,0,0.3); white-space: nowrap; z-index: 10;">
                            <div style="width: 14px; height: 14px; background-color: {color}; border-radius: 50%; 
                                        display: flex; align-items: center; justify-content: center; margin-right: 5px;">
                                <div style="transform: rotate({bearing}deg); color: white; font-size: 8px;">▲</div>
                            </div>
                            <div style="font-size: 12px; font-weight: bold; color: {color};">{bus_no}</div>
                        </div>
                        <div style="position: absolute; top: 25px; left: 5px; font-size: 9px; color: #333; 
                                    background: rgba(255,255,255,0.8); padding: 1px 3px; border-radius: 3px; z-index: 5;">
                            {status['curr']}
                        </div>
                    </div>
                    """
                    folium.Marker(
                        location=[lat, lon],
                        icon=folium.DivIcon(html=html, icon_size=(100, 50), icon_anchor=(15, 15))
                    ).add_to(m)
                    
        st_folium(m, width="100%", height=400, returned_objects=[])
        st.markdown("---")

        # 기존 하단 정보 출력 로직 온전히 복구
        for bus_no in target_buses:
            if bus_no not in bus_results: continue
            status, active_nodes = bus_results[bus_no]
            
            if status:
                curr_ord = status['ord']
                next_node_data = next((n for n in active_nodes if int(n['nodeord']) == curr_ord + 1), None)
                next_node_name = next_node_data['nodenm'] if next_node_data else "운행종료"
                
                st.write(f"[{bus_no}번]")
                st.write(f"현재 : {status['curr']}")
                st.write(f"다음 : {next_node_name}")
                
                eta_displayed = False
                
                if ref_name != "선택 안함" and target_node_id_for_api:
                    eta_text = get_arrival_info(target_node_id_for_api, bus_no, API_KEY, CITY_CODE)
                    if eta_text:
                        st.write(f"목표까지 : {eta_text} [{ref_name}]")
                        eta_displayed = True
                
                if not eta_displayed:
                    info = get_target_info(active_nodes, curr_ord, ref_name, bus_db)
                    if info: st.write(info)
                    
                st.caption(f"확인 시간 : {status['last_time']}")
                st.markdown("---")
            else:
                st.write(f"[{bus_no}번] 현재 정보 확인 불가")
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