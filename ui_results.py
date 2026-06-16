import html

import streamlit as st
import streamlit.components.v1 as components

from data_logic import NO_SELECTION, find_buses_at_node_indexed, get_route_id


def render_results(bus_db, bus_index):
    active_buses_data = []
    inactive_buses_data = []

    fetched_bus_nos = set()
    for res in st.session_state.get("bus_results_raw", []):
        bus_no, buses_active, status_msg = res
        fetched_bus_nos.add(bus_no)
        if status_msg == "정상" and buses_active:
            route_id = get_route_id(bus_db, bus_no)
            if route_id:
                active_buses_data.append((bus_no, buses_active, bus_db[bus_no][route_id]))
            else:
                inactive_buses_data.append((bus_no, "노선 정보 없음"))
        else:
            inactive_buses_data.append((bus_no, status_msg or "운행 종료 또는 지연"))

    for bus_no in st.session_state["active_buses"]:
        if bus_no not in fetched_bus_nos:
            inactive_buses_data.append((bus_no, "정보 없음"))

    active_count = sum(len(buses) for _, buses, _ in active_buses_data)
    col1, col2, col3 = st.columns(3)
    col1.metric("조회 노선", len(st.session_state["active_buses"]))
    col2.metric("운행 차량", active_count)
    col3.metric("갱신 주기", "15초")

    if st.session_state.get("last_fetch_seconds") is not None:
        st.caption(f"마지막 조회 처리 시간: {st.session_state['last_fetch_seconds']}초")

    scroll_targets = []

    with st.expander("상세 운행 노선 정보", expanded=True):
        active_ref_1 = st.session_state["active_ref_1"]
        active_ref_2 = st.session_state["active_ref_2"]

        if active_ref_1 != NO_SELECTION and active_ref_2 != NO_SELECTION:
            buses_1 = set(find_buses_at_node_indexed(bus_index, active_ref_1))
            buses_2 = set(find_buses_at_node_indexed(bus_index, active_ref_2))
            common_buses = sorted(buses_1.intersection(buses_2), key=str)
            if not common_buses:
                st.warning(f"'{active_ref_1}'와 '{active_ref_2}'를 모두 지나는 버스가 없습니다.")
            else:
                st.markdown(f"**[{active_ref_1}] - [{active_ref_2}] 경유 버스:** {', '.join(common_buses)}")
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
        elif active_ref_1 != NO_SELECTION:
            passing_buses = find_buses_at_node_indexed(bus_index, active_ref_1)
            st.markdown(f"**[{active_ref_1}] 경유 버스:** {', '.join(passing_buses)}")
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)

        for bus_no, buses_active, active_nodes in active_buses_data:
            st.markdown(
                f"<h4 style='color:#333;margin-bottom:5px;'>[{html.escape(str(bus_no))}번] 현재 {len(buses_active)}대 운행 중</h4>",
                unsafe_allow_html=True,
            )

            for idx, bus_status in enumerate(buses_active):
                curr_ord = bus_status["ord"]
                next_node_data = next((n for n in active_nodes if int(n["nodeord"]) == curr_ord + 1), None)
                next_node_name = next_node_data["nodenm"] if next_node_data else "운행 종료"

                title_suffix = (
                    f" <span style='font-size:14px;color:gray;'>({idx + 1}번째 차량)</span>"
                    if len(buses_active) > 1
                    else ""
                )
                st.markdown(f"**{bus_status['curr']} 통과** {title_suffix}", unsafe_allow_html=True)
                st.write(f"다음 정류장: {next_node_name}")
                st.caption(f"위치 확인 시각: {bus_status.get('last_time', '-')}")

                container_id = f"route-container-{bus_no}-{idx}"
                current_id = f"current-node-{bus_no}-{idx}"
                scroll_targets.append(current_id)

                path_spans = []
                for n in active_nodes:
                    n_ord = int(n["nodeord"])
                    n_name = html.escape(n["nodenm"])
                    if n_ord < curr_ord:
                        path_spans.append(f"<span style='color:#adb5bd;'>{n_name}</span>")
                    elif n_ord == curr_ord:
                        path_spans.append(
                            f"<span id='{current_id}' style='color:#d62728;font-weight:bold;font-size:15px;display:inline-block;'>[현재] {n_name}</span>"
                        )
                    else:
                        path_spans.append(f"<span style='color:#212529;'>{n_name}</span>")

                route_html = f"""
                <div id="{container_id}" style="overflow-x:auto;white-space:nowrap;padding:12px;background-color:#f8f9fa;border-radius:8px;font-size:13px;border:1px solid #e9ecef;margin-top:5px;margin-bottom:5px;">
                    {" &gt; ".join(path_spans)}
                </div>
                """
                st.markdown(route_html, unsafe_allow_html=True)
                st.write("")
            st.markdown("---")

        for bus_no, status in inactive_buses_data:
            st.markdown(f"**[{bus_no}번] 운행 정보 없음**")
            st.write(f"상태: {status}")
            st.markdown("---")

    if scroll_targets:
        js_lines = []
        for target_id in scroll_targets:
            safe_var = target_id.replace("-", "_")
            js_lines.append(
                f"""
                var {safe_var} = window.parent.document.getElementById('{target_id}');
                if ({safe_var} && {safe_var}.parentNode) {{
                    var parent = {safe_var}.parentNode;
                    var scrollPos = {safe_var}.offsetLeft - (parent.clientWidth / 2) + ({safe_var}.clientWidth / 2);
                    parent.scrollTo({{left: scrollPos, behavior: 'smooth'}});
                }}
                """
            )

        final_script = f"""
        <script>
            setTimeout(function() {{
                {"".join(js_lines)}
                window.parent.scrollTo({{top: 0, behavior: 'smooth'}});
            }}, 600);
        </script>
        """
        components.html(final_script, height=0, width=0)
