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
    """현재 버스 위치와 목표 정류장을 비교하여 남은 정거장 수와 색상을 반환합니다."""
    if ref_name == "선택 안함": 
        return None, "#1f77b4" # 기본 파란색
        
    target_node = next((n for n in nodes if n['nodenm'] == ref_name), None)
    
    if target_node:
        dist = int(target_node['nodeord']) - curr_ord
        if dist >= 0: 
            return f"{dist}정거장 전", "#d62728" # 빨간색 (다가오거나 도착)
        else: 
            return "지나침", "#7f7f7f" # 회색 (멀어짐)
            
    return None, "#1f77b4"