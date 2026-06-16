NO_SELECTION = "선택 안 함"


def get_route_id(bus_db, bus_no):
    routes = bus_db.get(bus_no)
    if not routes:
        return None
    return next(iter(routes.keys()), None)


def build_bus_index(bus_db):
    node_to_buses = {}
    node_lookup = {}
    unique_stations = {}

    for bus_no, routes in bus_db.items():
        for route in routes.values():
            for node in route:
                node_name = node["nodenm"]
                node_to_buses.setdefault(node_name, set()).add(bus_no)
                node_lookup.setdefault(node_name, node)
                unique_stations[node_name] = (
                    float(node["gpslati"]),
                    float(node["gpslong"]),
                )

    return {
        "all_nodes": sorted(node_lookup),
        "node_to_buses": node_to_buses,
        "node_lookup": node_lookup,
        "unique_stations": unique_stations,
    }


def find_buses_at_node(bus_db, node_name):
    index = build_bus_index(bus_db)
    return sorted(index["node_to_buses"].get(node_name, set()), key=str)


def find_buses_at_node_indexed(bus_index, node_name):
    return sorted(bus_index["node_to_buses"].get(node_name, set()), key=str)


def get_sorted_route(nodes):
    return sorted(nodes, key=lambda x: int(x["nodeord"]))


def get_target_info(nodes, curr_ord, ref_name, bus_db):
    if ref_name == NO_SELECTION:
        return ""
    target_node = next((n for n in nodes if n["nodenm"] == ref_name), None)

    if target_node:
        dist = int(target_node["nodeord"]) - curr_ord
        if dist == 0:
            return f"목표 정류장 [{ref_name}]"
        if dist > 0:
            return f"목표까지 {dist}정거장 남음 [{ref_name}]"
        return f"이미 지남 [{ref_name}]"
    return ""


def get_color_by_bus(bus_no):
    colors = [
        "#2563eb",
        "#dc2626",
        "#16a34a",
        "#d97706",
        "#7c3aed",
        "#0891b2",
        "#be123c",
        "#4d7c0f",
        "#9333ea",
        "#0f766e",
    ]
    idx = sum(ord(c) for c in str(bus_no)) % len(colors)
    return colors[idx]
