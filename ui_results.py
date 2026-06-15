import streamlit as st
import streamlit.components.v1 as components
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

    # 모든 버스의 현재 위치 ID를 수집할 리스트
    scroll_targets = []

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
                    
                    # 스크롤 대상을 리스트에 추가
                    scroll_targets.append(current_id)
                    
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
                    st.write("") 
                    
                st.markdown("---")

    # 수집된 모든 스크롤 대상을 한 번에 제어하는 통합 자바스크립트 실행
    if scroll_targets:
        js_lines = []
        for target_id in scroll_targets:
            safe_var = target_id.replace('-', '_')
            js_lines.append(f"""
                var {safe_var} = window.parent.document.getElementById('{target_id}');
                if ({safe_var}) {{
                    {safe_var}.scrollIntoView({{behavior: 'smooth', block: 'nearest', inline: 'center'}});
                }}
            """)
        
        combined_js = "\n".join(js_lines)
        final_script = f"""
        <script>
            setTimeout(function() {{
                {combined_js}
            }}, 600);
        </script>
        """
        # components.html을 사용하여 부모 DOM에 확실하게 접근
        components.html(final_script, height=0, width=0)