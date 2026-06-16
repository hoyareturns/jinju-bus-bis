import streamlit as st
from data_logic import find_buses_at_node

def render_controls(bus_db, fetch_locations_cached):
    st.title("금산버스 실시간 조회")

    target_input = st.text_input("조회할 버스번호 (쉼표 구분):", key="target_bus_input")
    search_term = st.text_input("정류장 검색어 입력:")

    all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
    filtered_nodes = [n for n in all_nodes if search_term in n] if search_term else all_nodes

    safe_nodes = set(filtered_nodes)
    if st.session_state["selected_node_1"] != "선택 안함": safe_nodes.add(st.session_state["selected_node_1"])
    if st.session_state["selected_node_2"] != "선택 안함": safe_nodes.add(st.session_state["selected_node_2"])
    options = ["선택 안함"] + sorted(list(safe_nodes))

    admin_mode = st.checkbox("관리자 모드: 모든 정류소 표시", key="admin_mode")
    st.markdown("**경로 찾기 (2개 선택 시 공통 버스 조회)**")

    idx_1 = options.index(st.session_state["selected_node_1"]) if st.session_state["selected_node_1"] in options else 0
    ref_name_1 = st.selectbox("목표 정류장 1:", options, index=idx_1)
    st.session_state["selected_node_1"] = ref_name_1

    if admin_mode:
        if st.button("목표 1 지도에서 선택", key="find_loc_1", use_container_width=True):
            st.session_state["map_select_mode"] = 1
        if st.session_state.get("map_select_mode") == 1:
            st.caption("지도에서 목표 1로 설정할 정류장을 클릭하세요.")

    idx_2 = options.index(st.session_state["selected_node_2"]) if st.session_state["selected_node_2"] in options else 0
    ref_name_2 = st.selectbox("목표 정류장 2:", options, index=idx_2)
    st.session_state["selected_node_2"] = ref_name_2

    if admin_mode:
        if st.button("목표 2 지도에서 선택", key="find_loc_2", use_container_width=True):
            st.session_state["map_select_mode"] = 2
        if st.session_state.get("map_select_mode") == 2:
            st.caption("지도에서 목표 2로 설정할 정류장을 클릭하세요.")

    with st.container():
        if st.button("목표노선 찾기 (조회)", type="primary", use_container_width=True):
            st.session_state["active_ref_1"] = ref_name_1
            st.session_state["active_ref_2"] = ref_name_2
            
            if ref_name_1 != "선택 안함" and ref_name_2 != "선택 안함":
                buses_1 = set(find_buses_at_node(bus_db, ref_name_1))
                buses_2 = set(find_buses_at_node(bus_db, ref_name_2))
                common_buses = sorted(list(buses_1.intersection(buses_2)), key=lambda x: str(x))
                st.session_state["target_bus_input"] = ", ".join(common_buses) if common_buses else ""

            st.session_state["active_buses"] = [b.strip() for b in st.session_state["target_bus_input"].split(",") if b.strip()]
            fetch_locations_cached.clear()
            st.session_state["needs_fetch"] = True
            st.rerun()

        if st.button("전체 데이터 새로고침", use_container_width=True):
            fetch_locations_cached.clear()
            st.session_state["needs_fetch"] = True
            st.rerun()