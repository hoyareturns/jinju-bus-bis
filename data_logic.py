from geopy.distance import geodesic
import hashlib

def find_buses_at_node(bus_db, node_name):
    found_buses = set()
    for b_no, routes in bus_db.items():
        for route in routes.values():
            if any(n['nodenm'] == node_name for n in route):
                found_buses.add(b_no)
    return sorted(list(found_buses), key=lambda x: str(x))

def get_sorted_route(nodes):
    return sorted(nodes, key=lambda x: int(x['nodeord']))

def get_target_info(nodes, curr_ord, ref_name):
    """현재 버스 위치와 목표 정류장을 비교하여 방향 상태를 반환합니다."""
    if ref_name == "선택 안함": 
        return None, "blue", ""
        
    target_node = next((n for n in nodes if n['nodenm'] == ref_name), None)
    
    if target_node:
        dist = int(target_node['nodeord']) - curr_ord
        if dist == 0: 
            return f"목표 도착 [{ref_name}]", "red", "🎯도착"
        elif dist > 0: 
            return f"목표까지 : {dist}정거장 남음 [{ref_name}]", "red", "⬇️다가옴"
        else: 
            return f"이미 지남 [{ref_name}]", "gray", "⬆️멀어짐"
            
    return None, "blue", ""

def get_color_by_bus(bus_no):
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    idx = sum(ord(c) for c in str(bus_no)) % len(colors)
    return colors[idx]