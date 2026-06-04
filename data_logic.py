from geopy.distance import geodesic

def find_buses_at_node(bus_db, node_name):
    """특정 정류장을 경유하는 모든 버스 번호를 찾습니다."""
    found_buses = []
    for b_no, routes in bus_db.items():
        for route in routes.values():
            if any(n['nodenm'] == node_name for n in route):
                found_buses.append(b_no)
    return found_buses

def get_sorted_route(nodes):
    """노선 데이터를 순번(nodeord) 기준으로 오름차순 정렬합니다."""
    return sorted(nodes, key=lambda x: int(x['nodeord']))

def get_target_info(nodes, curr_ord, ref_name, bus_db):
    """현재 위치와 목표 정류장 간의 거리/정거장 차이를 계산합니다."""
    if ref_name == "선택 안함":
        return ""
    
    target_node = next((n for n in nodes if n['nodenm'] == ref_name), None)
    
    if target_node:
        dist = int(target_node['nodeord']) - curr_ord
        if dist == 0:
            return f"목표: {ref_name} (현재 정류장)"
        elif dist > 0:
            return f"목표: {ref_name} ({dist}정거장 전)"
        else:
            return f"목표: {ref_name} (이미 지남)"
    else:
        # 노선에 목표가 없을 경우 좌표로 가장 가까운 정류장 찾기
        ref_coords = next(((s['gpslati'], s['gpslong']) for bus in bus_db.values() for r in bus.values() for s in r if s['nodenm'] == ref_name), None)
        if ref_coords:
            nearest = min(nodes, key=lambda n: geodesic((float(n['gpslati']), float(n['gpslong'])), ref_coords).meters)
            dist = int(nearest['nodeord']) - curr_ord
            return f"가까운 목표: {nearest['nodenm']} ({abs(dist)}정거장 차이)"
    
    return ""