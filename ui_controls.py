import streamlit as st

from data_logic import NO_SELECTION, find_buses_at_node_indexed


def _parse_bus_input(value):
    return [bus.strip() for bus in value.split(",") if bus.strip()]


def render_controls(bus_db, bus_index, fetch_locations_cached):
    st.markdown("<br>", unsafe_allow_html=True)

    target_input = st.text_input("조회할 버스 번호(쉼표로 구분)", key="target_bus_input")
    search_term = st.text_input("정류장 검색")

    all_nodes = bus_index["all_nodes"]
    filtered_nodes = [n for n in all_nodes if search_term in n] if search_term else all_nodes

    safe_nodes = set(filtered_nodes)
    if st.session_state["selected_node_1"] != NO_SELECTION:
        safe_nodes.add(st.session_state["selected_node_1"])
    if st.session_state["selected_node_2"] != NO_SELECTION:
        safe_nodes.add(st.session_state["selected_node_2"])
    options = [NO_SELECTION] + sorted(safe_nodes)

    st.checkbox("모든 정류장 지도에 표시", key="admin_mode")
    st.markdown("**경로 찾기: 정류장 2개를 선택하면 두 곳을 모두 지나는 버스를 찾습니다.**")

    btn_text_1 = f"목표 정류장 1: {st.session_state['selected_node_1']}\n지도에서 바꾸기"
    if st.button(btn_text_1, use_container_width=True):
        st.session_state["map_select_mode"] = 1
        st.session_state["admin_mode"] = True
        st.rerun()

    st.session_state["selected_node_1"] = st.selectbox(
        "목표 1 선택",
        options,
        index=options.index(st.session_state["selected_node_1"])
        if st.session_state["selected_node_1"] in options
        else 0,
        label_visibility="collapsed",
    )

    btn_text_2 = f"목표 정류장 2: {st.session_state['selected_node_2']}\n지도에서 바꾸기"
    if st.button(btn_text_2, use_container_width=True):
        st.session_state["map_select_mode"] = 2
        st.session_state["admin_mode"] = True
        st.rerun()

    st.session_state["selected_node_2"] = st.selectbox(
        "목표 2 선택",
        options,
        index=options.index(st.session_state["selected_node_2"])
        if st.session_state["selected_node_2"] in options
        else 0,
        label_visibility="collapsed",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("목표 노선 찾기", type="primary", use_container_width=True):
            st.session_state["active_ref_1"] = st.session_state["selected_node_1"]
            st.session_state["active_ref_2"] = st.session_state["selected_node_2"]

            ref_1 = st.session_state["selected_node_1"]
            ref_2 = st.session_state["selected_node_2"]
            if ref_1 != NO_SELECTION and ref_2 != NO_SELECTION:
                buses_1 = set(find_buses_at_node_indexed(bus_index, ref_1))
                buses_2 = set(find_buses_at_node_indexed(bus_index, ref_2))
                common_buses = sorted(buses_1.intersection(buses_2), key=str)
                st.session_state["target_bus_input"] = ", ".join(common_buses) if common_buses else ""

            st.session_state["active_buses"] = _parse_bus_input(st.session_state["target_bus_input"])
            fetch_locations_cached.clear()
            st.session_state["needs_fetch"] = True
            st.session_state["map_select_mode"] = 0
            st.rerun()

    with col2:
        if st.button("전체 데이터 새로고침", use_container_width=True):
            fetch_locations_cached.clear()
            st.session_state["active_buses"] = _parse_bus_input(target_input)
            st.session_state["needs_fetch"] = True
            st.session_state["admin_mode"] = False
            st.session_state["map_select_mode"] = 0
            st.rerun()
