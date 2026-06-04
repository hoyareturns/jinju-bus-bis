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

query_params = st.query_params
default_buses = query_params.get("buses", "360, 361, 362, 363")
# 목표 정류장 하드코딩 (없으면 무조건 금산우체국)
default_ref = query_params.get("ref", "금산우체국/금산푸르지오2단지")

# --- 사이드바 설정 영역 ---
st.sidebar.write("휴대폰 접속 QR")
current_qr_url = f"{BASE_URL}?buses={urllib.parse.quote(default_buses)}&ref={urllib.parse.quote(default_ref)}"
st.sidebar.image(get_qr_image(current_qr_url))
st.sidebar.markdown("---")

target_input = st.sidebar.text_input("버스번호 (쉼표 구분):", value=default_buses)

search_term = st.sidebar.text_input("정류장 검색어 입력:")
all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
filtered_nodes = [n for n in all_nodes if search_term in n] if search_term else all_nodes

options = ["선택 안함"] + filtered_nodes
# 리스트에 있으면 그 인덱스를, 없으면 0을 반환하여 강제 셋팅
ref_index = options.index(default_ref) if default_ref in options else 0
ref_name = st.sidebar.selectbox("목표 정류장 선택:", options, index=ref_index)

mode = st.sidebar.radio("보기 모드:", ["버스 위치 추적", "경유 버스 목록", "노선 순서 보기"])

if st.sidebar.button("새로고침"):
    st.rerun()

# URL 파라미터 업데이트
st.query_params["buses"] = target_input
st.query_params["ref"] = ref_name

# --- 메인 화면 영역 ---
st.title("금산버스")
st.markdown("---")

target_buses = [b.strip() for b in target_input.split(",") if b.strip()]

if mode == "버스 위치 추적":
    for bus_no in target_buses:
        if bus_no not in bus_db: continue
        
        status = None
        active_nodes = None
        for route_id, route_nodes in bus_db[bus_no].items():
            # 통신 시 retries=2 옵션으로 2번 더 재확인 수행
            loc_data = get_bus_location(bus_no, route_id, API_KEY, CITY_CODE, retries=2)
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
            st.caption(f"확인 시간 : {status['last_time']}")
        else:
            st.write(f"**{bus_no}번** : 현재 정보 확인 불가")
        st.markdown("---")

elif mode == "경유 버스 목록":
    if ref_name != "선택 안함":
        buses = find_buses_at_node(bus_db, ref_name)
        st.write(f"[{ref_name}] 경유 버스:")
        st.write(f"{', '.join(buses)}")

elif mode == "노선 순서 보기":
    for bus_no in target_buses:
        if bus_no in bus_db:
            nodes = list(bus_db[bus_no].values())[0]
            sorted_nodes = get_sorted_route(nodes)
            
            with st.expander(f"{bus_no}번 전체 노선 보기"):
                for n in sorted_nodes:
                    st.write(f"{n['nodeord']}. {n['nodenm']}")
        else:
            st.write(f"**{bus_no}번** : 노선 정보 없음")