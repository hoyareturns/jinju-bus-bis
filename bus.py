import streamlit as st
import json
from bus_utils import get_all_bus_locations_sync
from ui_sidebar import render_sidebar
from ui_controls import render_controls
from ui_map import render_map
from ui_results import render_results

API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]

st.set_page_config(page_title="금산버스", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""<style>.block-container { padding-top: 1rem; }</style>""", unsafe_allow_html=True)

# --- 세션 상태 초기화 ---
if "map_center" not in st.session_state: st.session_state["map_center"] = [35.1800, 128.1076]
if "zoom_level" not in st.session_state: st.session_state["zoom_level"] = 12
if "target_bus_input" not in st.session_state: st.session_state["target_bus_input"] = "10, 160, 360, 362, 363"
if "selected_node_1" not in st.session_state: st.session_state["selected_node_1"] = "금산우체국/금산푸르지오2단지"
if "selected_node_2" not in st.session_state: st.session_state["selected_node_2"] = "선택 안함"
if "active_ref_1" not in st.session_state: st.session_state["active_ref_1"] = "금산우체국/금산푸르지오2단지"
if "active_ref_2" not in st.session_state: st.session_state["active_ref_2"] = "선택 안함"
if "active_buses" not in st.session_state: st.session_state["active_buses"] = ["10", "160", "360", "362", "363"]
if "needs_fetch" not in st.session_state: st.session_state["needs_fetch"] = True
if "bus_results_raw" not in st.session_state: st.session_state["bus_results_raw"] = []
if "map_select_mode" not in st.session_state: st.session_state["map_select_mode"] = 0
if "last_clicked_pos" not in st.session_state: st.session_state["last_clicked_pos"] = None

@st.cache_data
def load_bus_data():
    with open('bus_data.json', 'r', encoding='utf-8') as f: return json.load(f)

@st.cache_data(ttl=30)
def fetch_locations_cached(targets, api_key, city_code):
    return get_all_bus_locations_sync(targets, api_key, city_code)

bus_db = load_bus_data()

# --- 화면 렌더링 파이프라인 ---
render_sidebar()
render_controls(bus_db, fetch_locations_cached)

# 통신 로직 (입력과 지도 렌더링 사이에 위치)
if st.session_state["needs_fetch"]:
    targets = []
    for bus_no in st.session_state["active_buses"]:
        if bus_no in bus_db:
            route_id = list(bus_db[bus_no].keys())[0]
            targets.append((bus_no, route_id))

    if targets:
        with st.spinner("최신 위치 정보를 가져오는 중..."):
            st.session_state["bus_results_raw"] = fetch_locations_cached(targets, API_KEY, CITY_CODE)
    else:
        st.session_state["bus_results_raw"] = []
    
    st.session_state["needs_fetch"] = False

render_map(bus_db)
render_results(bus_db)