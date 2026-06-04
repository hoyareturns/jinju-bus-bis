import streamlit as st
import json
import urllib.parse
from bus_utils import get_bus_location, get_qr_image
from data_logic import find_buses_at_node, get_target_info

API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]
# 본인의 실제 배포 주소를 아래에 넣으세요
BASE_URL = "https://jinju-bus-bis.streamlit.app" 

st.set_page_config(page_title="금산버스", layout="centered")

@st.cache_data
def load_bus_data():
    with open('bus_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

bus_db = load_bus_data()
st.title("금산버스")

if st.button("새로고침"):
    st.rerun()

query_params = st.query_params
default_buses = query_params.get("buses", "360, 361, 362, 363")
default_ref = query_params.get("ref", "선택 안함")

target_input = st.text_input("버스번호 (쉼표 구분):", value=default_buses)
all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
ref_name = st.selectbox("목표 정류장:", ["선택 안함"] + all_nodes, index=(["선택 안함"] + all_nodes).index(default_ref) if default_ref in all_nodes else 0)
mode = st.radio("보기 모드:", ["버스 위치 추적", "경유 버스 목록"], horizontal=True)

st.query_params["buses"] = target_input
st.query_params["ref"] = ref_name

current_qr_url = f"{BASE_URL}?buses={urllib.parse.quote(target_input)}&ref={urllib.parse.quote(ref_name)}"
st.sidebar.image(get_qr_image(current_qr_url))

st.markdown("---")

target_buses = [b.strip() for b in target_input.split(",") if b.strip()]

if mode == "버스 위치 추적":
    for bus_no in target_buses:
        if bus_no not in bus_db: continue
        route_id = list(bus_db[bus_no].keys())[0]
        status = get_bus_location(bus_no, route_id, API_KEY, CITY_CODE)
        
        if status:
            nodes = list(bus_db[bus_no].values())[0]
            next_node = next((n['nodenm'] for n in nodes if int(n['nodeord']) == status['ord'] + 1), "운행종료")
            st.write(f"**{bus_no}번**")
            st.write(f"현재 : {status['curr']}")
            st.write(f"다음 : {next_node}")
            info = get_target_info(nodes, status['ord'], ref_name, bus_db)
            if info: st.write(info)
            st.caption(f"기준시간 : {status['last_time']}")
        else:
            st.write(f"**{bus_no}번** : 정보 대기 중")
        st.markdown("---")

elif mode == "경유 버스 목록":
    if ref_name != "선택 안함":
        buses = find_buses_at_node(bus_db, ref_name)
        st.write(f"경유 버스: {', '.join(buses)}")