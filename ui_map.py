import streamlit as st
import folium
from streamlit_folium import st_folium
from bus_utils import get_bearing
from data_logic import get_color_by_bus

def render_map(bus_db):
    m = folium.Map(location=st.session_state["map_center"], zoom_start=st.session_state["zoom_level"], tiles="CartoDB positron")

    ref_name_1 = st.session_state["selected_node_1"]
    ref_name_2 = st.session_state["selected_node_2"]

    def get_node_coords(node_name):
        node_data = next((s for bus in bus_db.values() for r in bus.values() for s in r if s['nodenm'] == node_name), None)
        if node_data:
            return [float(node_data['gpslati']), float(node_data['gpslong'])]
        return None

    if ref_name_1 != "선택 안함":
        coords_1 = get_node_coords(ref_name_1)
        if coords_1: folium.Marker(location=coords_1, icon=folium.Icon(color='red', icon='flag', prefix='fa'), tooltip=ref_name_1).add_to(m)

    if ref_name_2 != "선택 안함":
        coords_2 = get_node_coords(ref_name_2)
        if coords_2: folium.Marker(location=coords_2, icon=folium.Icon(color='blue', icon='flag', prefix='fa'), tooltip=ref_name_2).add_to(m)

    if st.session_state["admin_mode"]:
        unique_stations = {}
        for b_data in bus_db.values():
            for r_data in b_data.values():
                for node in r_data:
                    unique_stations[node['nodenm']] = (float(node['gpslati']), float(node['gpslong']))
        
        for name, coords in unique_stations.items():
            if name not in [ref_name_1, ref_name_2]:
                html_station = f"""
                <div style="display: flex; align-items: center; white-space: nowrap;">
                    <div style="width: 8px; height: 8px; background-color: #71717a; border-radius: 50%; border: 1.5px solid white; box-shadow: 0 0 2px rgba(0,0,0,0.3);"></div>
                    <div style="font-size: 10px; color: #3f3f46; font-weight: bold; margin-left: 4px; background-color: rgba(255,255,255,0.85); padding: 1px 4px; border-radius: 4px; border: 0.5px solid #e4e4e7;">{name}</div>
                </div>
                """
                folium.Marker(location=coords, icon=folium.DivIcon(html=html_station, icon_anchor=(4, 4)), tooltip=name).add_to(m)

    # 💡 핵심 방어 로직: 대기 모드가 아닐 때는 클릭 신호를 무시하여 '뛰는 사람(로딩)' 발생 방지
    current_mode = st.session_state.get("map_select_mode", 0)
    ret_objs = []
    if current_mode in [1, 2]:
        ret_objs = ["last_object_clicked", "last_object_clicked_tooltip"]

    map_data = st_folium(m, height=400, use_container_width=True, returned_objects=ret_objs)

    # 대기 모드에서 지도 마커가 클릭되었을 때만 파이썬 변수 업데이트
    if current_mode in [1, 2] and map_data and map_data.get("last_object_clicked"):
        current_click_pos = map_data["last_object_clicked"]
        
        if current_click_pos != st.session_state.get("last_clicked_pos"):
            st.session_state["last_clicked_pos"] = current_click_pos
            clicked_name = map_data.get("last_object_clicked_tooltip")
            
            if clicked_name:
                if current_mode == 1:
                    st.session_state["selected_node_1"] = clicked_name
                elif current_mode == 2:
                    st.session_state["selected_node_2"] = clicked_name
                
                st.session_state["map_select_mode"] = 0
                st.rerun()