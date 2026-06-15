import streamlit as st
import urllib.parse
from bus_utils import get_qr_image
from data_logic import find_buses_at_node

BASE_URL = "https://jinju-bus-bis-bpesd99kxyupdbxgsuwvzt.streamlit.app" 

def render_sidebar(bus_db, fetch_locations_cached):
    st.sidebar.title("금산버스 설정")
    
    current_qr_url = f"{BASE_URL}?buses={urllib.parse.quote(st.session_state['target_bus_input'])}&ref={urllib.parse.quote(st.session_state['selected_node_1'])}"
    st.sidebar.image(get_qr_image(current_qr_url), caption="접속 QR")
    st.sidebar.markdown("---")

    target_input = st.sidebar.text_input("조회할 버스번호 (쉼표 구분):", key="target_bus_input")
    
    search_term = st.sidebar.text_input("정류장 검색어 입력:")
    all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
    filtered_nodes = [n for n in all_nodes if search_term in n] if search_term else all_nodes

    # 검색과 상관없이 현재 선택값을 리스트에 보존
    safe_nodes = set(filtered_nodes)
    if st.session_state["selected_node_1"] != "선택 안함":
        safe_nodes.add(st.session_state["selected_node_1"])
    if st.session_state["selected_node_2"] != "선택 안함":
        safe_nodes.add(st.session_state["selected_node_2"])
    options = ["선택 안함"] + sorted(list(safe_nodes))

    st.sidebar.checkbox("관리자 모드: 모든 정류소 표시", key="admin_mode")
    st.sidebar.markdown("---")
    st.sidebar.markdown("**경로 찾기 (2개 선택 시 공통 버스 조회)**")

    idx_1 = options.index(st.session_state["selected_node_1"]) if st.session_state["selected_node_1"] in options else 0
    ref_name_1 = st.sidebar.selectbox("목표 정류장 1:", options, index=idx_1)
    st.session_state["selected_node_1"] = ref_name_1

    if st.session_state["admin_mode"]:
        if st.sidebar.button("목표 1 지도에서 선택", key="find_loc_1", use_container_width=True):
            st.session_state["map_select_mode"] = 1
        if st.session_state.get("map_select_mode") == 1:
            st.sidebar.caption("지도에서 목표 1로 설정할 정류장을 클릭하세요.")

    idx_2 = options.index(st.session_state["selected_node_2"]) if st.session_state["selected_node_2"] in options else 0
    ref_name_2 = st.sidebar.selectbox("목표 정류장 2:", options, index=idx_2)
    st.session_state["selected_node_2"] = ref_name_2

    if st.session_state["admin_mode"]:
        if st.sidebar.button("목표 2 지도에서 선택", key="find_loc_2", use_container_width=True):
            st.session_state["map_select_mode"] = 2
        if st.session_state.get("map_select_mode") == 2:
            st.sidebar.caption("지도에서 목표 2로 설정할 정류장을 클릭하세요.")

    st.sidebar.markdown("---")

    # 목표노선 찾기 동작 시 텍스트 입력창 값 덮어쓰기 연동
    if st.sidebar.button("목표노선 찾기 (조회)", type="primary", use_container_width=True):
        st.session_state["active_ref_1"] = ref_name_1
        st.session_state["active_ref_2"] = ref_name_2
        
        if ref_name_1 != "선택 안함" and ref_name_2 != "선택 안함":
            buses_1 = set(find_buses_at_node(bus_db, ref_name_1))
            buses_2 = set(find_buses_at_node(bus_db, ref_name_2))
            common_buses = sorted(list(buses_1.intersection(buses_2)), key=lambda x: str(x))
            
            if common_buses:
                st.session_state["target_bus_input"] = ", ".join(common_buses)
            else:
                st.session_state["target_bus_input"] = ""

        st.session_state["active_buses"] = [b.strip() for b in st.session_state["target_bus_input"].split(",") if b.strip()]
        
        fetch_locations_cached.clear()
        st.session_state["needs_fetch"] = True
        st.rerun()

    st.sidebar.markdown("---")

    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("새로고침"):
            fetch_locations_cached.clear()
            st.session_state["needs_fetch"] = True
            st.rerun()