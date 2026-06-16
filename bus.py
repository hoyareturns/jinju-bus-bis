import json
import time

import streamlit as st

from bus_utils import get_all_bus_locations_sync
from data_logic import NO_SELECTION, build_bus_index, get_route_id
from ui_controls import render_controls
from ui_map import render_map
from ui_results import render_results
from ui_sidebar import render_sidebar


API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]
DEFAULT_BUSES = "10, 160, 360, 362, 363"
DEFAULT_CENTER = [35.1800, 128.1076]
DEFAULT_NODE_1 = "금산우체국/금산푸르지오2단지"


st.set_page_config(page_title="진주 버스 현황", layout="centered", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        div[data-testid="stMetricValue"] { font-size: 1.2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_session_state():
    defaults = {
        "map_center": DEFAULT_CENTER,
        "zoom_level": 12,
        "target_bus_input": DEFAULT_BUSES,
        "selected_node_1": DEFAULT_NODE_1,
        "selected_node_2": NO_SELECTION,
        "active_ref_1": DEFAULT_NODE_1,
        "active_ref_2": NO_SELECTION,
        "active_buses": [b.strip() for b in DEFAULT_BUSES.split(",")],
        "needs_fetch": True,
        "bus_results_raw": [],
        "map_select_mode": 0,
        "last_clicked_pos": None,
        "admin_mode": False,
        "last_fetch_seconds": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


@st.cache_data
def load_bus_data():
    with open("bus_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_bus_index():
    return build_bus_index(load_bus_data())


@st.cache_data(ttl=15, show_spinner=False)
def fetch_locations_cached(targets, api_key, city_code):
    return get_all_bus_locations_sync(targets, api_key, city_code)


init_session_state()
bus_db = load_bus_data()
bus_index = load_bus_index()

render_sidebar()
render_controls(bus_db, bus_index, fetch_locations_cached)

if st.session_state["needs_fetch"]:
    targets = []
    missing_buses = []
    for bus_no in st.session_state["active_buses"]:
        route_id = get_route_id(bus_db, bus_no)
        if route_id:
            targets.append((bus_no, route_id))
        else:
            missing_buses.append((bus_no, [], "노선 정보 없음"))

    if targets:
        with st.spinner("최신 위치 정보를 가져오는 중..."):
            start_time = time.perf_counter()
            st.session_state["bus_results_raw"] = fetch_locations_cached(targets, API_KEY, CITY_CODE)
            st.session_state["last_fetch_seconds"] = round(time.perf_counter() - start_time, 2)
    else:
        st.session_state["bus_results_raw"] = []
        st.session_state["last_fetch_seconds"] = 0

    st.session_state["bus_results_raw"].extend(missing_buses)
    st.session_state["needs_fetch"] = False

render_map(bus_db, bus_index)
render_results(bus_db, bus_index)
