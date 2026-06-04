import streamlit as st
import json
import urllib.parse
from bus_utils import get_bus_location, get_qr_image
from data_logic import find_buses_at_node, get_sorted_route, get_target_info

API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]

# 반드시 실제 배포된 주소로 변경해 주세요.
BASE_URL = "https://jinju-bus-bis.streamlit.app" 

st.set_page_config(page_title="진주 BIS 관제", layout="centered")

st.markdown("""
    <link rel="manifest" href="static/manifest.json">
    <meta name="theme-color" content="#FF4B4B">
""", unsafe_allow_html=True)

@st.cache_data
def load_bus_data():
    with open('bus_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

bus_db = load_bus_data()

if 'bus_status' not in st.session_state:
    st.session_state.bus_status = {}

query_params = st.query_params
default_buses = query_params.get("buses", "360, 361, 362, 363")
default_ref = query_params.get("ref", "선택 안함")

st.title("진주시 실시간 BIS 관제")

all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))

target_input = st.text_input("추적할 버스번호 (쉼표 구분):", value=default_buses)

if default_ref in all_nodes:
    ref_index = (["선택 안함"] + all_nodes).index(default_ref)
else:
    ref_index = 0
ref_name = st.selectbox("목표(기준) 정류장:", ["선택 안함"] + all_nodes, index=ref_index)

mode = st.radio("작동 모드:", ["버스 위치 추적", "경유 버스 목록", "노선 순서 보기"])

st.query_params["buses"] = target_input
st.query_params["ref"] = ref_name

encoded_buses = urllib.parse.quote(target_input)
encoded_ref = urllib.parse.quote(ref_name)
current_qr_url = f"{BASE_URL}?buses={encoded_buses}&ref={encoded_ref}"

st.sidebar.write("휴대폰 접속 QR")
st.sidebar.image(get_qr_image(current_qr_url), width=150)

st.markdown("---")

target_buses = [b.strip() for b in target_input.split(",") if b.strip()]

if mode == "버스 위치 추적":
    for bus_no in target_buses:
        if bus_no not in bus_db:
            st.error(f"{bus_no}번: 노선 정보 없음")
            continue

        route_id = list(bus_db[bus_no].keys())[0]
        
        loc_data = get_bus_location(bus_no, route_id, API_KEY, CITY_CODE)
        if loc_data:
            st.session_state.bus_status[bus_no] = loc_data

        status = st.session_state.bus_status.get(bus_no)
        
        if status:
            nodes = list(bus_db[bus_no].values())[0]
            curr_ord = status['ord']
            
            next_node = next((n['nodenm'] for n in nodes if int(n['nodeord']) == curr_ord + 1), "운행종료")
            
            target_info = get_target_info(nodes, curr_ord, ref_name, bus_db)
            
            st.write(f"**{bus_no}번**")
            st.write(f"현재 : {status['curr']}")
            st.write(f"다음 : {next_node}")
            if target_info:
                st.write(target_info)
            st.caption(f"마지막 확인 : {status['last_time']}")
        else:
            st.write(f"**{bus_no}번**")
            st.write("운행 정보 대기 중...")
            
        st.markdown("---")
        
    if st.button("새로고침"):
        st.rerun()

elif mode == "경유 버스 목록":
    if ref_name != "선택 안함":
        found_buses = find_buses_at_node(bus_db, ref_name)
        if found_buses:
            st.write(f"[{ref_name}] 경유 버스:")
            st.write(f"{', '.join(found_buses)}")
        else:
            st.write("해당 정류장을 지나는 버스가 없습니다.")
    else:
        st.write("목표 정류장을 선택해 주세요.")

elif mode == "노선 순서 보기":
    for bus_no in target_buses:
        if bus_no in bus_db:
            nodes = list(bus_db[bus_no].values())[0]
            sorted_nodes = get_sorted_route(nodes)
            
            with st.expander(f"{bus_no}번 노선"):
                for n in sorted_nodes:
                    st.write(f"{n['nodeord']}. {n['nodenm']}")
        else:
            st.write(f"{bus_no}번: 노선 정보 없음")