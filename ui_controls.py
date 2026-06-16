import streamlit as st
from data_logic import find_buses_at_node

def render_controls(bus_db, fetch_locations_cached):
    # 타이틀 삭제 및 상단 여백 추가
    st.markdown("<br>", unsafe_allow_html=True)

    target_input = st.text_input("조회할 버스번호 (쉼표 구분):", key="target_bus_input")
    search_term = st.text_input("정류장 검색어 입력:")

    all_nodes = sorted(list(set(s['nodenm'] for bus in bus_db.values() for route in bus.values() for s in route)))
    filtered_nodes = [n for n in all_nodes if search_term in n] if search_term else all_nodes

    safe_nodes = set(filtered_nodes)
    if st.session_state["selected_node_1"] != "선택 안함": safe_nodes.add(st.session_state["selected_node_1"])
    if st.session_state["selected_node_2"] != "선택 안함": safe_nodes.add(st.session_state["selected_node_2"])
    options = ["선택 안함"] + sorted(list(safe_nodes))

    st.checkbox("모든 정류소 표시", key="admin_mode")
    st.markdown("**경로 찾기 (2개 선택 시 공통 버스 조회)**")

    # --- 목표 1 통합 UI ---
    btn_text_1 = f"목표 정류장 1: {st.session_state['selected_node_1']}\n(변경시 여기를 클릭후 지도에서 선택)"
    if st.button(btn_text_1, use_container_width=True):
        st.session_state["map_select_mode"] = 1
        st.session_state["admin_mode"] = True
        st.rerun()
    
    # 텍스트 검색 시 선택 가능하도록 공간 낭비 없는 드롭다운 연동
    st.session_state["selected_node_1"] = st.selectbox(
        "목표 1 선택", 
        options, 
        index=options.index(st.session_state["selected_node_1"]) if st.session_state["selected_node_1"] in options else 0, 
        label_visibility="collapsed"
    )

    # --- 목표 2 통합 UI ---
    btn_text_2 = f"목표 정류장 2: {st.session_state['selected_node_2']}\n(변경시 여기를 클릭후 지도에서 선택)"
    if st.button(btn_text_2, use_container_width=True):
        st.session_state["map_select_mode"] = 2
        st.session_state["admin_mode"] = True
        st.rerun()

    st.session_state["selected_node_2"] = st.selectbox(
        "목표 2 선택", 
        options, 
        index=options.index(st.session_state["selected_node_2"]) if st.session_state["selected_node_2"] in options else 0, 
        label_visibility="collapsed"
    )

    with st.container():
        if st.button("목표노선 찾기 (조회)", type="primary", use_container_width=True):
            st.session_state["active_ref_1"] = st.session_state["selected_node_1"]
            st.session_state["active_ref_2"] = st.session_state["selected_node_2"]
            
            ref_1 = st.session_state["selected_node_1"]
            ref_2 = st.session_state["selected_node_2"]
            if ref_1 != "선택 안함" and ref_2 != "선택 안함":
                buses_1 = set(find_buses_at_node(bus_db, ref_1))
                buses_2 = set(find_buses_at_node(bus_db, ref_2))
                common_buses = sorted(list(buses_1.intersection(buses_2)), key=lambda x: str(x))
                st.session_state["target_bus_input"] = ", ".join(common_buses) if common_buses else ""

            st.session_state["active_buses"] = [b.strip() for b in st.session_state["target_bus_input"].split(",") if b.strip()]
            fetch_locations_cached.clear()
            st.session_state["needs_fetch"] = True
            st.session_state["map_select_mode"] = 0
            st.rerun()

        if st.button("전체 데이터 새로고침", use_container_width=True):
            fetch_locations_cached.clear()
            st.session_state["needs_fetch"] = True
            st.session_state["admin_mode"] = False
            st.session_state["map_select_mode"] = 0
            st.rerun()