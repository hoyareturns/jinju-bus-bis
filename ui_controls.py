import streamlit as st

from data_logic import NO_SELECTION, find_buses_at_node_indexed


def _parse_bus_input(value):
    return [bus.strip() for bus in value.split(",") if bus.strip()]


def _short_name(name, limit=18):
    if not name or name == NO_SELECTION:
        return NO_SELECTION
    return name if len(name) <= limit else f"{name[:limit]}..."


def _apply_map_station(slot):
    station = st.session_state.get("map_clicked_station")
    if not station:
        return

    key = "selected_node_1" if slot == 1 else "selected_node_2"
    st.session_state[key] = station
    st.session_state["map_select_mode"] = 0
    node = st.session_state.get("bus_index", {}).get("node_lookup", {}).get(station)
    if node:
        st.session_state["map_center"] = [float(node["gpslati"]), float(node["gpslong"])]


def render_controls(bus_db, bus_index, fetch_locations_cached):
    st.session_state["bus_index"] = bus_index
    if "pending_admin_mode" in st.session_state:
        st.session_state["admin_mode"] = st.session_state.pop("pending_admin_mode")

    st.markdown("<br>", unsafe_allow_html=True)

    target_input = st.text_input("버스 번호", key="target_bus_input", help="쉼표로 여러 번호를 입력")
    search_term = st.text_input("정류장 검색", placeholder="정류장명")

    all_nodes = bus_index["all_nodes"]
    filtered_nodes = [n for n in all_nodes if search_term in n] if search_term else all_nodes

    safe_nodes = set(filtered_nodes)
    if st.session_state["selected_node_1"] != NO_SELECTION:
        safe_nodes.add(st.session_state["selected_node_1"])
    if st.session_state["selected_node_2"] != NO_SELECTION:
        safe_nodes.add(st.session_state["selected_node_2"])
    if st.session_state.get("map_clicked_station"):
        safe_nodes.add(st.session_state["map_clicked_station"])
    options = [NO_SELECTION] + sorted(safe_nodes)

    st.checkbox("정류장 지도 표시", key="admin_mode")

    clicked_station = st.session_state.get("map_clicked_station")
    if clicked_station:
        st.caption(f"지도 선택: {clicked_station}")
        col_pick_1, col_pick_2 = st.columns(2)
        with col_pick_1:
            if st.button("목표1로", use_container_width=True):
                _apply_map_station(1)
                st.rerun()
        with col_pick_2:
            if st.button("목표2로", use_container_width=True):
                _apply_map_station(2)
                st.rerun()

    col_view_1, col_view_2 = st.columns(2)
    with col_view_1:
        if st.button(f"목표1 지도: {_short_name(st.session_state['selected_node_1'])}", use_container_width=True):
            st.session_state["pending_admin_mode"] = True
            st.rerun()
    with col_view_2:
        if st.button(f"목표2 지도: {_short_name(st.session_state['selected_node_2'])}", use_container_width=True):
            st.session_state["pending_admin_mode"] = True
            st.rerun()

    st.session_state["selected_node_1"] = st.selectbox(
        "목표 1",
        options,
        index=options.index(st.session_state["selected_node_1"])
        if st.session_state["selected_node_1"] in options
        else 0,
    )

    st.session_state["selected_node_2"] = st.selectbox(
        "목표 2",
        options,
        index=options.index(st.session_state["selected_node_2"])
        if st.session_state["selected_node_2"] in options
        else 0,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("노선 찾기", type="primary", use_container_width=True):
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
            st.rerun()

    with col2:
        if st.button("새로고침", use_container_width=True):
            fetch_locations_cached.clear()
            st.session_state["active_buses"] = _parse_bus_input(target_input)
            st.session_state["needs_fetch"] = True
            st.rerun()
