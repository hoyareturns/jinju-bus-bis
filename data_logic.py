from geopy.distance import geodesic

def find_buses_at_node(bus_db, node_name):
    found_buses = set()
    for b_no, routes in bus_db.items():
        for route in routes.values():
            if any(n['nodenm'] == node_name for n in route):
                found_buses.add(b_no)
    return sorted(list(found_buses), key=lambda x: str(x))

def get_sorted_route(nodes):
    return sorted(nodes, key=lambda x: int(x['nodeord']))

def get_target_info(nodes, curr_ord, ref_name, bus_db):
    if ref_name == "선택 안함": return ""
    target_node = next((n for n in nodes if n['nodenm'] == ref_name), None)
    
    if target_node:
        dist = int(target_node['nodeord']) - curr_ord
        if dist == 0: 
            return f"목표 도착 [{ref_name}]"
        elif dist > 0: 
            # 1정거장당 약 2분 소요로 단순 계산
            eta_mins = dist * 2
            return f"목표까지 : {dist}정거장 남음 (약 {eta_mins}분 후 예상) [{ref_name}]"
        else: 
            return f"이미 지남 [{ref_name}]"
    return ""