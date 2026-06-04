import streamlit as st
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import json
from geopy.distance import geodesic  # <--- 이 부분이 반드시 필요합니다!

API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]

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

st.title("🚌 진주시 실시간 BIS 관제")

target_input = st.text_input("추적할 버스번호 (쉼표 구분):", "360, 150, 250")
target_buses = [b.strip() for b in target_input.split(",") if b.strip()]

all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
default_ref = "금산우체국/금산푸르지오2단지" if "금산우체국/금산푸르지오2단지" in all_nodes else (all_nodes[0] if all_nodes else "선택 안함")
ref_name = st.selectbox("목표(기준) 정류장:", ["선택 안함"] + all_nodes, 
                        index=(["선택 안함"] + all_nodes).index(default_ref) if default_ref in all_nodes else 0)

st.markdown("---")

for bus_no in target_buses:
    if bus_no not in bus_db:
        st.write(f"🚌 {bus_no}번: 노선 정보 없음")
        st.markdown("────────────────────────")
        continue

    route_id = list(bus_db[bus_no].keys())[0]
    url = f"http://apis.data.go.kr/1613000/BusLcInfoInqireService/getRouteAcctoBusLcList?serviceKey={API_KEY}&cityCode={CITY_CODE}&routeId={route_id}&numOfRows=10&_type=xml"
    
    try:
        res = requests.get(url, timeout=3)
        root = ET.fromstring(res.content)
        item = root.find('.//item')
        if item is not None:
            st.session_state.bus_status[bus_no] = {
                "curr": item.find('nodenm').text,
                "ord": int(item.find('nodeord').text),
                "last_time": datetime.now().strftime("%H시 %M분")
            }
    except: pass

    status = st.session_state.bus_status.get(bus_no)
    if status:
        curr_ord = status['ord']
        nodes = list(bus_db[bus_no].values())[0]
        next_node = next((n['nodenm'] for n in nodes if int(n['nodeord']) == curr_ord + 1), "운행종료")
        
        target_info = "목표 없음"
        if ref_name != "선택 안함":
            target_node = next((n for n in nodes if n['nodenm'] == ref_name), None)
            
            if target_node:
                dist = int(target_node['nodeord']) - curr_ord
                target_info = f"목표 : {ref_name} ({dist}정거장)" if dist >= 0 else f"목표 : {ref_name} (이미 지남)"
            else:
                ref_coords = next(((s['gpslati'], s['gpslong']) for bus in bus_db.values() for r in bus.values() for s in r if s['nodenm'] == ref_name), None)
                if ref_coords:
                    nearest = min(nodes, key=lambda n: geodesic((float(n['gpslati']), float(n['gpslong'])), ref_coords).meters)
                    dist = int(nearest['nodeord']) - curr_ord
                    target_info = f"가까운 목표 : {nearest['nodenm']} ({abs(dist)}정거장)"
                else:
                    target_info = ""

        st.write(f"🚌 {bus_no}번")
        st.write(f"현재 : {status['curr']}")
        st.write(f"다음 : {next_node}")
        st.write(target_info)
        st.write(f"마지막 확인 : {status['last_time']}")
        st.markdown("────────────────────────")
    else:
        st.write(f"🚌 {bus_no}번: 운행 정보 대기 중...")
        st.markdown("────────────────────────")

if st.button("새로고침"):
    st.rerun()