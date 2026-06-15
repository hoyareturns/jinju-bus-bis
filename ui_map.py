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

    bus_results_raw = st.session_state.get("bus_results_raw", [])
    seen_coords = {}
    for res in bus_results_raw:
        bus_no, buses_active, status_msg = res
        if status_msg == "정상" and buses_active:
            route_id = list(bus_db[bus_no].keys())[0]
            active_nodes = bus_db[bus_no][route_id]
            for bus_status in buses_active:
                curr_ord = bus_status['ord']
                curr_node = next((n for n in active_nodes if int(n['nodeord']) == curr_ord), None)
                next_node_data = next((n for n in active_nodes if int(n['nodeord']) == curr_ord + 1), None)
                
                if curr_node:
                    lat, lon = float(curr_node['gpslati']), float(curr_node['gpslong'])
                    color = get_color_by_bus(bus_no)
                    
                    bearing = 0
                    if next_node_data:
                        n_lat = float(next_node_data['gpslati'])
                        n_lon = float(next_node_data['gpslong'])
                        bearing = get_bearing(lat, lon, n_lat, n_lon)
                        
                    coord_key = f"{lat:.4f}_{lon:.4f}"
                    if coord_key in seen_coords:
                        lat += (0.00025 * seen_coords[coord_key])
                        lon -= (0.00025 * seen_coords[coord_key])
                        seen_coords[coord_key] += 1
                    else:
                        seen_coords[coord_key] = 1
                    
                    html = f"""
                    <div style="position: relative; width: 40px; height: 40px;">
                        <div style="position: absolute; left: 14px; top: 14px; width: 14px; height: 14px; background-color: {color}; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 10;">
                            <div style="transform: rotate({bearing}deg); color: white; font-size: 10px; font-weight: bold; line-height: 1;">&uarr;</div>
                        </div>
                        <div style="position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%); background-color: white; border: 2px solid {color}; border-radius: 6px; padding: 3px 6px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); white-space: nowrap; z-index: 5;">
                            <div style="font-size: 12px; font-weight: bold; color: {color};">{bus_no}</div>
                            <div style="font-size: 10px; color: #333; font-weight: bold;">{bus_status['curr']}</div>
                        </div>
                        <div style="position: absolute; bottom: 24px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid {color}; z-index: 4;"></div>
                    </div>
                    """
                    folium.Marker(location=[lat, lon], icon=folium.DivIcon(html=html, icon_size=(40, 40), icon_anchor=(20, 20))).add_to(m)

    map_data = st_folium(m, height=450, use_container_width=True, returned_objects=["last_object_clicked", "last_object_clicked_tooltip", "center", "zoom"])

    # 사용자가 마우스로 이동한 위치 기억 보존 (화면 튕김 방지)
    if map_data and map_data.get("center") and map_data.get("zoom"):
        st.session_state["map_center"] = [map_data["center"]["lat"], map_data["center"]["lng"]]
        st.session_state["zoom_level"] = map_data["zoom"]

    # 지도에서 정류장 직접 클릭 시 목표 1, 2 자동 값 입력
    if map_data and map_data.get("last_object_clicked"):
        current_click_pos = map_data["last_object_clicked"]
        if current_click_pos != st.session_state.get("last_clicked_pos"):
            st.session_state["last_clicked_pos"] = current_click_pos
            clicked_name = map_data.get("last_object_clicked_tooltip")
            
            if clicked_name:
                if st.session_state.get("map_select_mode") == 1:
                    st.session_state["selected_node_1"] = clicked_name
                    st.session_state["map_select_mode"] = 0
                    st.rerun()
                elif st.session_state.get("map_select_mode") == 2:
                    st.session_state["selected_node_2"] = clicked_name
                    st.session_state["map_select_mode"] = 0
                    st.rerun()