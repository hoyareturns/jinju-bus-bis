import streamlit as st
from data_logic import find_buses_at_node

def render_results(bus_db):
    active_ref_1 = st.session_state["active_ref_1"]
    active_ref_2 = st.session_state["active_ref_2"]
    target_buses = st.session_state["active_buses"]
    bus_results_raw = st.session_state["bus_results_raw"]

    common_buses = []
    if active_ref_1 != "선택 안함" and active_ref_2 != "선택 안함":
        buses_1 = set(find_buses_at_node(bus_db, active_ref_1))
        buses_2 = set(find_buses_at_node(bus_db, active_ref_2))
        common_buses = sorted(list(buses_1.intersection(buses_2)), key=lambda x: str(x))

    with st.expander("상세 운행 노선 정보", expanded=True):
        
        if active_ref_1 != "선택 안함" and active_ref_2 != "선택 안함":
            if not target_buses:
                st.warning(f"'{active_ref_1}'과 '{active_ref_2}'를 모두 지나는 직행 버스가 없습니다.")
            st.markdown(f"**[{active_ref_1}] ↔ [{active_ref_2}] 직행 버스:** &nbsp;` {', '.join(common_buses) if common_buses else '없음'} `")
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
        elif active_ref_1 != "선택 안함":
            passing_buses = find_buses_at_node(bus_db, active_ref_1)
            st.markdown(f"**[{active_ref_1}] 경유 버스:** &nbsp;` {', '.join(passing_buses)} `")
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            
        bus_results = {}
        for res in bus_results_raw:
            bus_no, buses_active, status_msg = res
            if status_msg == "정상" and buses_active:
                route_id = list(bus_db[bus_no].keys())[0]
                bus_results[bus_no] = (buses_active, bus_db[bus_no][route_id])

        for bus_no in target_buses:
            err_msg = next((res[2] for res in bus_results_raw if res[0] == bus_no), None)
            if err_msg and err_msg != "정상":
                st.error(f"[{bus_no}번] {err_msg}")
                st.markdown("---")
                continue
                
            if bus_no in bus_results:
                buses_active, active_nodes = bus_results[bus_no]
                st.markdown(f"<h4 style='color:#333; margin-bottom: 5px;'>[{bus_no}번] 현재 {len(buses_active)}대 운행 중</h4>", unsafe_allow_html=True)
                
                for idx, bus_status in enumerate(buses_active):
                    curr_ord = bus_status['ord']
                    next_node_data = next((n for n in active_nodes if int(n['nodeord']) == curr_ord + 1), None)
                    next_node_name = next_node_data['nodenm'] if next_node_data else "운행종료"
                    
                    title_suffix = f" <span style='font-size:14px; color:gray;'>( {idx+1}호차 )</span>" if len(buses_active) > 1 else ""
                    st.markdown(f"**{bus_status['curr']} 통과** {title_suffix}", unsafe_allow_html=True)
                    st.write(f"▶ 다음 정류장 : {next_node_name}")
                    
                    container_id = f"route-container-{bus_no}-{idx}"
                    current_id = f"current-node-{bus_no}-{idx}"
                    
                    path_spans = []
                    for n in active_nodes:
                        n_ord = int(n['nodeord'])
                        n_name = n['nodenm']
                        if n_ord < curr_ord:
                            path_spans.append(f"<span style='color:#adb5bd;'>{n_name}</span>")
                        elif n_ord == curr_ord:
                            path_spans.append(f"<span id='{current_id}' style='color:#d62728; font-weight:bold; font-size: 15px; display:inline-block;'>[현재] {n_name}</span>")
                        else:
                            path_spans.append(f"<span style='color:#212529;'>{n_name}</span>")
                    
                    route_html = f"""
                    <div id="{container_id}" style="overflow-x: auto; white-space: nowrap; padding: 12px; background-color: #f8f9fa; border-radius: 8px; font-size: 13px; border: 1px solid #e9ecef; margin-top:5px; margin-bottom:5px;">
                        {" &gt; ".join(path_spans)}
                    </div>
                    """
                    st.markdown(route_html, unsafe_allow_html=True)
                    
                    js_scroll = f"""
                    <script>
                        setTimeout(function() {{
                            var element = document.getElementById('{current_id}');
                            if (element) {{
                                element.scrollIntoView({{behavior: 'smooth', block: 'nearest', inline: 'center'}});
                            }}
                        }}, 400);
                    </script>
                    """
                    st.markdown(js_scroll, unsafe_allow_html=True)
                    st.write("") 
                    
                st.markdown("---")