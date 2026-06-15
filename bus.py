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

# --- 세션 상태 초기화 ---
if "map_center" not in st.session_state:
    st.session_state["map_center"] = [35.1800, 128.1076]
if "zoom_level" not in st.session_state:
    st.session_state["zoom_level"] = 12
if "fit_bounds" not in st.session_state:
    st.session_state["fit_bounds"] = None

query_params = st.query_params
default_buses = query_params.get("buses", "10, 160, 360, 362, 363")
default_ref = query_params.get("ref", "금산우체국/금산푸르지오2단지")

# 동적 선택 컴포넌트 및 활성화(Active) 타겟 분리
if "selected_node_1" not in st.session_state:
    st.session_state["selected_node_1"] = default_ref
if "selected_node_2" not in st.session_state:
    st.session_state["selected_node_2"] = "선택 안함"

if "active_ref_1" not in st.session_state:
    st.session_state["active_ref_1"] = default_ref
if "active_ref_2" not in st.session_state:
    st.session_state["active_ref_2"] = "선택 안함"
if "active_buses" not in st.session_state:
    st.session_state["active_buses"] = [b.strip() for b in default_buses.split(",") if b.strip()]

# 💡 통신 제어용 변수 (앱 첫 실행 시 True로 시작, 이후엔 버튼 클릭 시에만 True로 변경)
if "needs_fetch" not in st.session_state:
    st.session_state["needs_fetch"] = True
if "bus_results_raw" not in st.session_state:
    st.session_state["bus_results_raw"] = []

@st.cache_data
def load_bus_data():
    with open('bus_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

bus_db = load_bus_data()

@st.cache_data(ttl=30)
def fetch_locations_cached(targets, api_key, city_code):
    return get_all_bus_locations_sync(targets, api_key, city_code)

def get_node_coords(node_name):
    node_data = next((s for bus in bus_db.values() for r in bus.values() for s in r if s['nodenm'] == node_name), None)
    if node_data:
        return [float(node_data['gpslati']), float(node_data['gpslong'])]
    return None

# --- 1. 사이드바 설정 영역 ---
st.sidebar.title("금산버스 설정")
current_qr_url = f"{BASE_URL}?buses={urllib.parse.quote(default_buses)}&ref={urllib.parse.quote(default_ref)}"
st.sidebar.image(get_qr_image(current_qr_url), caption="접속 QR")
st.sidebar.markdown("---")

target_input = st.sidebar.text_input("조회할 버스번호 (쉼표 구분):", value=default_buses)
manual_target_buses = [b.strip() for b in target_input.split(",") if b.strip()]

search_term = st.sidebar.text_input("정류장 검색어 입력:")
all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
filtered_nodes = [n for n in all_nodes if search_term in n] if search_term else all_nodes

options = ["선택 안함"] + filtered_nodes

# 관리자 모드를 위로 배치하여 아래 버튼들의 활성화 상태를 직관적으로 제어
admin_mode = st.sidebar.checkbox("⚙️ 관리자 모드: 모든 정류소 표시", value=False)
st.sidebar.markdown("---")

st.sidebar.markdown("**경로 찾기 (2개 선택 시 공통 버스 조회)**")

# 입력 필드 1
idx_1 = options.index(st.session_state["selected_node_1"]) if st.session_state["selected_node_1"] in options else 0
ref_name_1 = st.sidebar.selectbox("목표 정류장 1:", options, index=idx_1)
st.session_state["selected_node_1"] = ref_name_1

# 💡 관리자 모드가 선택된 상태에서만 '지도에서 찾기' 활성화
if admin_mode:
    if st.sidebar.button("🔍 목표 1 지도에서 찾기", key="find_loc_1", use_container_width=True):
        if ref_name_1 == "선택 안함" and filtered_nodes:
            ref_name_1 = filtered_nodes[0]
            st.session_state["selected_node_1"] = ref_name_1
            
        if ref_name_1 != "선택 안함":
            coords = get_node_coords(ref_name_1)
            if coords:
                st.session_state["map_center"] = coords
                st.session_state["zoom_level"] = 15
                st.session_state["fit_bounds"] = None
                st.rerun()

# 입력 필드 2
idx_2 = options.index(st.session_state["selected_node_2"]) if st.session_state["selected_node_2"] in options else 0
ref_name_2 = st.sidebar.selectbox("목표 정류장 2:", options, index=idx_2)
st.session_state["selected_node_2"] = ref_name_2

# 💡 관리자 모드가 선택된 상태에서만 '지도에서 찾기' 활성화
if admin_mode:
    if st.sidebar.button("🔍 목표 2 지도에서 찾기", key="find_loc_2", use_container_width=True):
        if ref_name_2 == "선택 안함" and filtered_nodes:
            ref_name_2 = filtered_nodes[0]
            st.session_state["selected_node_2"] = ref_name_2
            
        if ref_name_2 != "선택 안함":
            coords = get_node_coords(ref_name_2)
            if coords:
                st.session_state["map_center"] = coords
                st.session_state["zoom_level"] = 15
                st.session_state["fit_bounds"] = None
                st.rerun()

st.sidebar.markdown("---")

# 🚀 찐 통신 트리거 버튼 (이 버튼을 눌러야만 검색이 시작됨)
if st.sidebar.button("🚀 목표노선 찾기 (조회)", type="primary", use_container_width=True):
    st.session_state["active_ref_1"] = ref_name_1
    st.session_state["active_ref_2"] = ref_name_2
    st.session_state["active_buses"] = manual_target_buses
    
    fetch_locations_cached.clear() # 캐시 비우기
    st.session_state["needs_fetch"] = True # 통신 신호 ON
    
    bounds_to_fit = []
    if ref_name_1 != "선택 안함":
        c1 = get_node_coords(ref_name_1)
        if c1: bounds_to_fit.append(c1)
    if ref_name_2 != "선택 안함":
        c2 = get_node_coords(ref_name_2)
        if c2: bounds_to_fit.append(c2)
        
    if len(bounds_to_fit) == 2:
        st.session_state["fit_bounds"] = bounds_to_fit
    elif len(bounds_to_fit) == 1:
        st.session_state["map_center"] = bounds_to_fit[0]
        st.session_state["zoom_level"] = 14
    st.rerun()

st.sidebar.markdown("---")


# --- 2. 최상단 새로고침 컨트롤 ---
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("🔄 새로고침"):
        fetch_locations_cached.clear()
        st.session_state["zoom_level"] = 12
        st.session_state["map_center"] = [35.1800, 128.1076]
        st.session_state["fit_bounds"] = None
        st.session_state["needs_fetch"] = True # 통신 신호 ON
        st.rerun()


# --- 3. 데이터 로드 및 지도 렌더링 ---
m = folium.Map(location=st.session_state["map_center"], zoom_start=st.session_state["zoom_level"], tiles="CartoDB positron")

# 깃발은 현재 UI에서 선택된(선택 변경 중인) 위치를 바로 보여줌 (통신 무관)
if ref_name_1 != "선택 안함":
    coords_1 = get_node_coords(ref_name_1)
    if coords_1: folium.Marker(location=coords_1, icon=folium.Icon(color='red', icon='flag', prefix='fa'), tooltip=ref_name_1).add_to(m)

if ref_name_2 != "선택 안함":
    coords_2 = get_node_coords(ref_name_2)
    if coords_2: folium.Marker(location=coords_2, icon=folium.Icon(color='blue', icon='flag', prefix='fa'), tooltip=ref_name_2).add_to(m)

if st.session_state.get("fit_bounds"):
    m.fit_bounds(st.session_state["fit_bounds"], padding=(30, 30))
    st.session_state["fit_bounds"] = None

# 관리자 모드 정류소 표시 레이어
if admin_mode:
    unique_stations = {}
    for b_data in bus_db.values():
        for r_data in b_data.values():
            for node in r_data:
                unique_stations[node['nodenm']] = (float(node['gpslati']), float(node['gpslong']))
    
    for name, coords in unique_stations.items():
        if name not in [ref_name_1, ref_name_2]:
            html_station = f"""
            <div style="display: flex; align-items: center; white-space: nowrap;">
                <div style="width: 8px; height: 8px; background-color: #71717a; border-radius: 50%; border: 1.5px solid white; box-shadow: 0 0 2px rgba(0,0,0,0.3);"></div>
                <div style="font-size: 10px; color: #3f3f46; font-weight: bold; margin-left: 4px; background-color: rgba(255,255,255,0.85); padding: 1px 4px; border-radius: 4px; border: 0.5px solid #e4e4e7;">{name}</div>
            </div>
            """
            folium.Marker(
                location=coords,
                icon=folium.DivIcon(html=html_station, icon_anchor=(4, 4)),
                tooltip=name
            ).add_to(m)


# --- 4. 🚀 실질적인 검색 로직 및 상태 유지 (통신 철저 제어) ---
active_ref_1 = st.session_state["active_ref_1"]
active_ref_2 = st.session_state["active_ref_2"]
target_buses = st.session_state["active_buses"]
common_buses = []

if active_ref_1 != "선택 안함" and active_ref_2 != "선택 안함":
    buses_1 = set(find_buses_at_node(bus_db, active_ref_1))
    buses_2 = set(find_buses_at_node(bus_db, active_ref_2))
    common_buses = sorted(list(buses_1.intersection(buses_2)), key=lambda x: str(x))
    target_buses = common_buses

targets = []
for bus_no in target_buses:
    if bus_no in bus_db:
        route_id = list(bus_db[bus_no].keys())[0]
        targets.append((bus_no, route_id))

# 교집합이 없을 경우
if active_ref_1 != "선택 안함" and active_ref_2 != "선택 안함" and not target_buses:
    st.warning(f"⚠️ '{active_ref_1}'과 '{active_ref_2}'를 모두 지나는 직행 버스가 없습니다.")
    st.session_state["bus_results_raw"] = []
else:
    # 💡 사용자가 명시적으로 통신을 지시(needs_fetch=True)했을 때만 API를 호출합니다.
    if st.session_state["needs_fetch"]:
        if targets:
            with st.spinner("🚀 최신 위치 정보를 가져오는 중..."):
                st.session_state["bus_results_raw"] = fetch_locations_cached(targets, API_KEY, CITY_CODE)
        else:
            st.session_state["bus_results_raw"] = []
        # 통신이 끝났으므로 신호를 차단하여 다음 화면 새로고침 시 무단 통신 방지
        st.session_state["needs_fetch"] = False

# 항상 세션에 안전하게 저장된(캐싱된) 데이터를 바탕으로 화면을 그립니다.
bus_results = {}
seen_coords = {} 
bus_results_raw = st.session_state["bus_results_raw"]

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
                    n_lat = float(next_node_data['gpslati'])
                    n_lon = float(next_node_data['gpslong'])
                    bearing = get_bearing(lat, lon, n_lat, n_lon)
                    
                coord_key = f"{lat:.4f}_{lon:.4f}"
                if coord_key in seen_coords:
                    offset_count = seen_coords[coord_key]
                    lat += (0.00025 * offset_count)
                    lon -= (0.00025 * offset_count)
                    seen_coords[coord_key] += 1
                else:
                    seen_coords[coord_key] = 1
                
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
                folium.Marker(location=[lat, lon], icon=folium.DivIcon(html=html, icon_size=(40, 40), icon_anchor=(20, 20))).add_to(m)

st_folium(m, height=450, use_container_width=True, returned_objects=[])


# --- 5. 하단 상세 정보 영역 ---
with st.expander("상세 운행 노선 정보", expanded=True):
    
    if active_ref_1 != "선택 안함" and active_ref_2 != "선택 안함":
        st.markdown(f"🎯 **[{active_ref_1}] ↔ [{active_ref_2}] 직행 버스:** &nbsp;` {', '.join(common_buses) if common_buses else '없음'} `")
        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    elif active_ref_1 != "선택 안함":
        passing_buses = find_buses_at_node(bus_db, active_ref_1)
        st.markdown(f"📢 **[{active_ref_1}] 경유 버스:** &nbsp;` {', '.join(passing_buses)} `")
        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
        
    for bus_no in target_buses:
        err_msg = next((res[2] for res in bus_results_raw if res[0] == bus_no), None)
        if err_msg and err_msg != "정상":
            st.error(f"[{bus_no}번] {err_msg}")
            st.markdown("---")
            continue
            
        if bus_no in bus_results:
            buses_active, active_nodes = bus_results[bus_no]
            st.markdown(f"<h4 style='color:#333; margin-bottom: 5px;'>[{bus_no}번] 현재 {len(buses_active)}대 운행 중</h4>", unsafe_allow_html=True)
            
            for idx, bus_status in enumerate(buses_active):
                curr_ord = bus_status['ord']
                next_node_data = next((n for n in active_nodes if int(n['nodeord']) == curr_ord + 1), None)
                next_node_name = next_node_data['nodenm'] if next_node_data else "운행종료"
                
                title_suffix = f" <span style='font-size:14px; color:gray;'>( {idx+1}호차 )</span>" if len(buses_active) > 1 else ""
                st.markdown(f"**{bus_status['curr']} 통과** {title_suffix}", unsafe_allow_html=True)
                st.write(f"▶ 다음 정류장 : {next_node_name}")
                
                container_id = f"route-container-{bus_no}-{idx}"
                current_id = f"current-node-{bus_no}-{idx}"
                
                path_spans = []
                for n in active_nodes:
                    n_ord = int(n['nodeord'])
                    n_name = n['nodenm']
                    if n_ord < curr_ord:
                        path_spans.append(f"<span style='color:#adb5bd;'>{n_name}</span>")
                    elif n_ord == curr_ord:
                        path_spans.append(f"<span id='{current_id}' style='color:#d62728; font-weight:bold; font-size: 15px; display:inline-block;'>📍{n_name}(현재)</span>")
                    else:
                        path_spans.append(f"<span style='color:#212529;'>{n_name}</span>")
                
                route_html = f"""
                <div id="{container_id}" style="overflow-x: auto; white-space: nowrap; padding: 12px; background-color: #f8f9fa; border-radius: 8px; font-size: 13px; border: 1px solid #e9ecef; margin-top:5px; margin-bottom:5px;">
                    {" &gt; ".join(path_spans)}
                </div>
                """
                st.markdown(route_html, unsafe_allow_html=True)
                
                js_scroll = f"""
                <script>
                    setTimeout(function() {{
                        var element = document.getElementById('{current_id}');
                        if (element) {{
                            element.scrollIntoView({{behavior: 'smooth', block: 'nearest', inline: 'center'}});
                        }}
                    }}, 400);
                </script>
                """
                st.markdown(js_scroll, unsafe_allow_html=True)
                st.write("") 
                
            st.markdown("---")