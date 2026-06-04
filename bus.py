import streamlit as st
import json
import urllib.parse
from bus_utils import get_bus_location, get_qr_image
from data_logic import find_buses_at_node, get_sorted_route, get_target_info

API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]
BASE_URL = "https://jinju-bus-bis.streamlit.app" # 본인의 배포 주소에 맞게 수정하세요.

st.set_page_config(page_title="진주 BIS 관제", layout="wide")

# PWA 설정
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

# URL 파라미터에서 기존 설정값 읽어오기 (없으면 기본값 사용)
query_params = st.query_params
default_buses = query_params.get("buses", "360, 150, 250")
default_ref = query_params.get("ref", "선택 안함")

st.title("진주시 실시간 BIS 관제")

all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))

# 메인 화면 상단 제어판 구성
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)
with col_ctrl1:
    target_input = st.text_input("추적할 버스번호 (쉼표 구분):", value=default_buses)
with col_ctrl2:
    if default_ref in all_nodes:
        ref_index = (["선택 안함"] + all_nodes).index(default_ref)
    else:
        ref_index = 0
    ref_name = st.selectbox("목표(기준) 정류장:", ["선택 안함"] + all_nodes, index=ref_index)
with col_ctrl3:
    mode = st.radio("작동 모드:", ["버스 위치 추적", "경유 버스 목록", "노선 순서 보기"], horizontal=True)

# 사용자가 화면에서 수정한 값을 URL 파라미터에 즉시 동기화
st.query_params["buses"] = target_input
st.query_params["ref"] = ref_name

# 현재 화면 설정값이 포함된 동적 QR URL 주소 생성
encoded_buses = urllib.parse.quote(target_input)
encoded_ref = urllib.parse.quote(ref_name)
current_qr_url = f"{BASE_URL}?buses={encoded_buses}&ref={encoded_ref}"

# 사이드바 UI (파라미터가 연동된 QR 코드만 배치)
st.sidebar.write("휴대폰 접속 QR")
st.sidebar.image(get_qr_image(current_qr_url), width=150)

st.markdown("---")

target_buses = [b.strip() for b in target_input.split(",") if b.strip()]

# 모드 1: 실시간 위치 추적
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
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader(f"{bus_no}번 버스")
            if status:
                nodes = list(bus_db[bus_no].values())[0]
                curr_ord = status['ord']
                
                target_info = get_target_info(nodes, curr_ord, ref_name, bus_db)
                
                st.write(f"**현재 위치:** {status['curr']}")
                if target_info:
                    st.write(f"**목표 정보:** {target_info}")
            else:
                st.write("운행 정보 대기 중...")
                
        with col2:
            if status:
                st.metric("마지막 확인", status['last_time'])
        st.markdown("---")
        
    if st.button("새로고침"):
        st.rerun()

# 모드 2: 특정 정류장 경유 노선 검색
elif mode == "경유 버스 목록":
    st.subheader(f"'{ref_name}' 경유 노선")
    if ref_name != "선택 안함":
        found_buses = find_buses_at_node(bus_db, ref_name)
        if found_buses:
            st.success(f"경유 버스 리스트: {', '.join(found_buses)}")
        else:
            st.warning("해당 정류장을 지나는 버스가 데이터에 없습니다.")
    else:
        st.info("목표(기준) 정류장을 선택해 주세요.")

# 모드 3: 선택한 버스의 전체 노선도
elif mode == "노선 순서 보기":
    st.subheader("선택 버스 노선도")
    for bus_no in target_buses:
        if bus_no in bus_db:
            nodes = list(bus_db[bus_no].values())[0]
            sorted_nodes = get_sorted_route(nodes)
            
            with st.expander(f"{bus_no}번 버스 전체 노선"):
                for n in sorted_nodes:
                    st.write(f"{n['nodeord']}. {n['nodenm']}")
        else:
            st.error(f"{bus_no}번: 노선 정보 없음")