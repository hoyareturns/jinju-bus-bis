import html

import folium
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from bus_utils import get_bearing
from data_logic import NO_SELECTION, get_color_by_bus, get_route_id


def render_map(bus_db, bus_index):
    m = folium.Map(
        location=st.session_state["map_center"],
        zoom_start=st.session_state["zoom_level"],
        tiles="CartoDB positron",
        control_scale=True,
    )

    ref_name_1 = st.session_state["selected_node_1"]
    ref_name_2 = st.session_state["selected_node_2"]

    def get_node_coords(node_name):
        node_data = bus_index["node_lookup"].get(node_name)
        if node_data:
            return [float(node_data["gpslati"]), float(node_data["gpslong"])]
        return None

    if ref_name_1 != NO_SELECTION:
        coords_1 = get_node_coords(ref_name_1)
        if coords_1:
            folium.Marker(
                location=coords_1,
                icon=folium.Icon(color="red", icon="flag"),
                tooltip=f"목표1: {ref_name_1}",
            ).add_to(m)

    if ref_name_2 != NO_SELECTION:
        coords_2 = get_node_coords(ref_name_2)
        if coords_2:
            folium.Marker(
                location=coords_2,
                icon=folium.Icon(color="blue", icon="flag"),
                tooltip=f"목표2: {ref_name_2}",
            ).add_to(m)

    if st.session_state.get("admin_mode"):
        cluster = MarkerCluster(
            name="정류장",
            disableClusteringAtZoom=16,
            spiderfyOnMaxZoom=True,
            showCoverageOnHover=False,
        ).add_to(m)
        for name, coords in bus_index["unique_stations"].items():
            if name in [ref_name_1, ref_name_2]:
                continue
            safe_name = html.escape(name)
            folium.CircleMarker(
                location=coords,
                radius=5,
                color="#475569",
                fill=True,
                fill_color="#f8fafc",
                fill_opacity=0.9,
                weight=2,
                tooltip=name,
            ).add_to(cluster)

    seen_coords = {}
    for res in st.session_state.get("bus_results_raw", []):
        bus_no, buses_active, status_msg = res
        if status_msg != "정상" or not buses_active:
            continue

        route_id = get_route_id(bus_db, bus_no)
        if not route_id:
            continue
        active_nodes = bus_db[bus_no][route_id]

        for bus_status in buses_active:
            curr_ord = bus_status["ord"]
            curr_node = next((n for n in active_nodes if int(n["nodeord"]) == curr_ord), None)
            next_node_data = next((n for n in active_nodes if int(n["nodeord"]) == curr_ord + 1), None)

            if not curr_node:
                continue

            lat = float(curr_node["gpslati"])
            lon = float(curr_node["gpslong"])
            color = get_color_by_bus(bus_no)

            bearing = 0
            if next_node_data:
                bearing = get_bearing(
                    lat,
                    lon,
                    float(next_node_data["gpslati"]),
                    float(next_node_data["gpslong"]),
                )

            coord_key = f"{lat:.4f}_{lon:.4f}"
            offset_count = seen_coords.get(coord_key, 0)
            if offset_count:
                lat += 0.00025 * offset_count
                lon -= 0.00025 * offset_count
            seen_coords[coord_key] = offset_count + 1

            safe_bus_no = html.escape(str(bus_no))
            safe_curr = html.escape(bus_status["curr"])
            marker_html = f"""
            <div style="position:relative;width:34px;height:34px;">
                <div style="position:absolute;left:10px;top:10px;width:14px;height:14px;background-color:{color};border-radius:50%;border:2px solid white;box-shadow:0 0 4px rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:10;">
                    <div style="transform:rotate({bearing}deg);color:white;font-size:10px;font-weight:bold;line-height:1;">&uarr;</div>
                </div>
                <div style="position:absolute;bottom:25px;left:50%;transform:translateX(-50%);background-color:white;border:2px solid {color};border-radius:6px;padding:2px 5px;box-shadow:1px 1px 4px rgba(0,0,0,0.25);white-space:nowrap;z-index:5;">
                    <div style="font-size:11px;font-weight:bold;color:{color};">{safe_bus_no}</div>
                    <div style="font-size:9px;color:#333;font-weight:bold;max-width:95px;overflow:hidden;text-overflow:ellipsis;">{safe_curr}</div>
                </div>
            </div>
            """
            folium.Marker(
                location=[lat, lon],
                icon=folium.DivIcon(html=marker_html, icon_size=(34, 34), icon_anchor=(17, 17)),
                tooltip=f"{bus_no} {bus_status['curr']}",
            ).add_to(m)

    ret_objs = ["last_object_clicked", "last_object_clicked_tooltip"]
    map_data = st_folium(m, height=360, use_container_width=True, returned_objects=ret_objs)

    if map_data and map_data.get("last_object_clicked"):
        clicked_name = map_data.get("last_object_clicked_tooltip")
        if clicked_name in bus_index["node_lookup"]:
            current_click_pos = map_data["last_object_clicked"]
            if current_click_pos != st.session_state.get("last_clicked_pos"):
                st.session_state["last_clicked_pos"] = current_click_pos
                st.session_state["map_clicked_station"] = clicked_name
                node_coords = get_node_coords(clicked_name)
                if node_coords:
                    st.session_state["map_center"] = node_coords
                st.rerun()
