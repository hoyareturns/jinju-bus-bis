import streamlit as st
import json
import urllib.parse
from bus_utils import get_bus_location, get_qr_image
from data_logic import find_buses_at_node, get_sorted_route, get_target_info

API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]
BASE_URL = "https://jinju-bus-bis-bpesd99kxyupdbxgsuwvzt.streamlit.app" 

st.set_page_config(page_title="금산버스", layout="centered")

@st.cache_data
def load_bus_data():
    with open('bus_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

bus_db = load_bus_data()
st.title("금산버스")

# URL 파라미터 및 기본값 설정 (금산우체국 초기화 반영)
query_params = st.query_params
default_buses = query_params.get("buses", "360, 361, 362, 363")
default_ref = query_params.get("ref", "금산우체국/금산푸르지오2단지")

target_input = st.text_input("버스번호 (쉼표 구분):", value=default_buses)

# 정류장 검색 기능
search_term = st.text_input("정류장 검색어 입력:")
all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
filtered_nodes = [n for n in all_nodes if search_term in n] if search_term else all_nodes

# 선택 리스트 구성
options = ["선택 안함"] + filtered_nodes
ref_index = options.index(default_ref) if default_ref in options else 0
ref_name = st.selectbox("목표 정류장 선택:", options, index=ref_index)

# 보기 모드 및 새로고침 버튼 (순서 배치 반영)
mode = st.radio("보기 모드:", ["버스 위치 추적", "경유 버스 목록", "노선 순서 보기"], horizontal=True)

if st.button("새로고침"):
    st.rerun()

st.query_params["buses"] = target_input
st.query_params["ref"] = ref_name

current_qr_url = f"{BASE_URL}?buses={urllib.parse.quote(target_input)}&ref={urllib.parse.quote(ref_name)}"
st.sidebar.image(get_qr_image(current_qr_url))

st.markdown("---")

target_buses = [b.strip() for b in target_input.split(",") if b.strip()]

if mode == "버스 위치 추적":
    for bus_no in target_buses:
        if bus_no not in bus_db: continue
        
        # 상행/하행 모든 노선을 확인하여 버스를 찾음
        status = None
        active_nodes = None
        for route_id, route_nodes in bus_db[bus_no].items():
            loc_data = get_bus_location(bus_no, route_id, API_KEY, CITY_CODE)
            if loc_data:
                status = loc_data
                active_nodes = route_nodes
                break
        
        if status:
            next_node = next((n['nodenm'] for n in active_nodes if int(n['nodeord']) == status['ord'] + 1), "운행종료")
            st.write(f"**{bus_no}번**")
            st.write(f"현재 : {status['curr']}")
            st.write(f"다음 : {next_node}")
            info = get_target_info(active_nodes, status['ord'], ref_name, bus_db)
            if info: st.write(info)
            st.caption(f"기준시간 : {status['last_time']}")
        else:
            # 대기중 문구 변경
            st.write(f"**{bus_no}번** : 현재 정보 확인 불가")
        st.markdown("---")

elif mode == "경유 버스 목록":
    if ref_name != "선택 안함":
        buses = find_buses_at_node(bus_db, ref_name)
        st.write(f"[{ref_name}] 경유 버스:")
        st.write(f"{', '.join(buses)}")

# 누락되었던 노선 순서 보기 기능 복구
elif mode == "노선 순서 보기":
    for bus_no in target_buses:
        if bus_no in bus_db:
            # 첫 번째 노선 기준 전체 정류장 출력
            nodes = list(bus_db[bus_no].values())[0]
            sorted_nodes = get_sorted_route(nodes)
            
            with st.expander(f"{bus_no}번 전체 노선 보기"):
                for n in sorted_nodes:
                    st.write(f"{n['nodeord']}. {n['nodenm']}")
        else:
            st.write(f"**{bus_no}번** : 노선 정보 없음")