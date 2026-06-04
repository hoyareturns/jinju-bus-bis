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
    if ref_name == "선택 안함":
        return ""
    
    target_node = next((n for n in nodes if n['nodenm'] == ref_name), None)
    
    if target_node:
        dist = int(target_node['nodeord']) - curr_ord
        if dist == 0:
            return f"목표에 도착했습니다. [{ref_name}]"
        elif dist > 0:
            return f"목표까지 : {dist}정거장 남음. [{ref_name}]"
        else:
            return f"목표를 이미 지났습니다. [{ref_name}]"
    else:
        ref_coords = next(((s['gpslati'], s['gpslong']) for bus in bus_db.values() for r in bus.values() for s in r if s['nodenm'] == ref_name), None)
        if ref_coords:
            nearest = min(nodes, key=lambda n: geodesic((float(n['gpslati']), float(n['gpslong'])), ref_coords).meters)
            dist = int(nearest['nodeord']) - curr_ord
            return f"가까운 목표까지 : {abs(dist)}정거장 차이. [{nearest['nodenm']}]"
    
    return ""