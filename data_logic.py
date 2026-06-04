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

def get_target_info(nodes, curr_ord, ref_name, bus_db):
    if ref_name == "선택 안함": return ""
    target_node = next((n for n in nodes if n['nodenm'] == ref_name), None)
    
    if target_node:
        dist = int(target_node['nodeord']) - curr_ord
        if dist == 0: 
            return f"목표 도착 [{ref_name}]"
        elif dist > 0: 
            return f"목표까지 : {dist}정거장 남음 [{ref_name}]"
        else: 
            return f"이미 지남 [{ref_name}]"
    return ""

def get_color_by_bus(bus_no):
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    hash_val = int(hashlib.md5(bus_no.encode()).hexdigest(), 16)
    return colors[hash_val % len(colors)]