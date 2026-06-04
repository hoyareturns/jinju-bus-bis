import streamlit as st
import json
from bus_utils import get_bus_location, get_qr_image
from data_logic import find_buses_at_node, get_sorted_route, get_target_info

# --- 1. 설정 및 변수 ---
API_KEY = st.secrets["API_KEY"]
CITY_CODE = st.secrets["CITY_CODE"]
QR_URL = "https://jinju-bus-bis.streamlit.app" # 배포 후 할당받은 주소로 꼭 변경하세요!

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

# --- 2. 사이드바 UI ---
st.sidebar.title("⚙️ 관제 설정")
target_input = st.sidebar.text_input("추적할 버스번호 (쉼표 구분):", "360, 150, 250")
all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
ref_name = st.sidebar.selectbox("목표(기준) 정류장:", ["선택 안함"] + all_nodes)

mode = st.sidebar.radio("작동 모드:", ["버스 위치 추적", "경유 버스 목록", "노선 순서 보기"])

st.sidebar.markdown("---")
st.sidebar.write("📱 휴대폰으로 바로 접속 (QR)")
st.sidebar.image(get_qr_image(QR_URL), width=150)

# --- 3. 메인 화면 로직 ---
st.title("🚌 진주시 실시간 BIS 관제")
target_buses = [b.strip() for b in target_input.split(",") if b.strip()]

# 모드 1: 실시간 위치 추적
if mode == "버스 위치 추적":
    for bus_no in target_buses:
        if bus_no not in bus_db:
            st.error(f"{bus_no}번: 노선 정보 없음")
            continue

        route_id = list(bus_db[bus_no].keys())[0]
        
        # bus_utils 모듈에서 위치 가져오기
        loc_data = get_bus_location(bus_no, route_id, API_KEY, CITY_CODE)
        if loc_data:
            st.session_state.bus_status[bus_no] = loc_data

        status = st.session_state.bus_status.get(bus_no)
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader(f"🚌 {bus_no}번 버스")
            if status:
                nodes = list(bus_db[bus_no].values())[0]
                curr_ord = status['ord']
                
                # data_logic 모듈에서 목표 정보 계산하기
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
    st.subheader(f"📍 '{ref_name}' 경유 노선")
    if ref_name != "선택 안함":
        found_buses = find_buses_at_node(bus_db, ref_name)
        if found_buses:
            st.success(f"경유 버스 리스트: {', '.join(found_buses)}")
        else:
            st.warning("해당 정류장을 지나는 버스가 데이터에 없습니다.")
    else:
        st.info("사이드바에서 '목표(기준) 정류장'을 선택해 주세요.")

# 모드 3: 선택한 버스의 전체 노선도
elif mode == "노선 순서 보기":
    st.subheader("🚌 선택 버스 노선도")
    for bus_no in target_buses:
        if bus_no in bus_db:
            nodes = list(bus_db[bus_no].values())[0]
            sorted_nodes = get_sorted_route(nodes)
            
            with st.expander(f"{bus_no}번 버스 전체 노선"):
                for n in sorted_nodes:
                    st.write(f"{n['nodeord']}. {n['nodenm']}")
        else:
            st.error(f"{bus_no}번: 노선 정보 없음")