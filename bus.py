import streamlit as st
import json, urllib.parse, folium
from streamlit_folium import st_folium
from concurrent.futures import ThreadPoolExecutor
from bus_utils import get_bus_location, get_qr_image, get_bearing, get_arrival_info
from data_logic import find_buses_at_node, get_sorted_route, get_target_info, get_color_by_bus

API_KEY, CITY_CODE = st.secrets["API_KEY"], st.secrets["CITY_CODE"]
BASE_URL = "https://jinju-bus-bis-bpesd99kxyupdbxgsuwvzt.streamlit.app"
st.set_page_config(page_title="금산버스", layout="centered")

@st.cache_data
def load_bus_data():
    with open('bus_data.json', 'r', encoding='utf-8') as f: return json.load(f)

bus_db = load_bus_data()
params = st.query_params
bus_val = params.get("buses", "10, 160, 360, 362, 363")
ref_val = params.get("ref", "금산우체국/금산푸르지오2단지")

# 사이드바 설정
st.sidebar.title("금산버스 설정")
st.sidebar.image(get_qr_image(f"{BASE_URL}?buses={urllib.parse.quote(bus_val)}&ref={urllib.parse.quote(ref_val)}"))
target_input = st.sidebar.text_input("버스번호 (쉼표 구분):", value=bus_val)
all_nodes = sorted(list(set(s['nodenm'] for b in bus_db.values() for r in b.values() for s in r)))
ref_name = st.sidebar.selectbox("목표 정류장 선택:", ["선택 안함"] + all_nodes, index=["선택 안함"] + all_nodes.index(ref_val) if ref_val in all_nodes else 0)
mode = st.sidebar.radio("보기 모드:", ["버스 위치 추적", "경유 버스 목록", "노선 순서 보기"])

if st.button("새로고침"): st.rerun()
st.query_params.update({"buses": target_input, "ref": ref_name})

def fetch_worker(b):
    for r_id, nodes in bus_db.get(b, {}).items():
        loc = get_bus_location(b, r_id, API_KEY, CITY_CODE)
        if loc: return b, loc, nodes
    return b, None, None

if mode == "버스 위치 추적":
    with st.spinner("정보 불러오는 중..."):
        m = folium.Map(location=[35.18, 128.10], zoom_start=13, tiles="CartoDB positron")
        # 목적지 깃발
        ref_n = next((s for b in bus_db.values() for r in b.values() for s in r if s['nodenm'] == ref_name), None)
        if ref_n: folium.Marker([float(ref_n['gpslati']), float(ref_n['gpslong'])], icon=folium.DivIcon(html=f'<div style="font-size:10px; font-weight:bold; color:red; border:1px solid red; background:white; padding:2px; border-radius:3px;">{ref_name}</div>')).add_to(m)
        
        with ThreadPoolExecutor(max_workers=5) as executor: results = list(executor.map(fetch_worker, [b.strip() for b in target_input.split(",")]))
        
        for b, status, nodes in results:
            if status:
                curr = next(n for n in nodes if int(n['nodeord']) == status['ord'])
                nxt = next((n for n in nodes if int(n['nodeord']) == status['ord']+1), None)
                lat, lon = float(curr['gpslati']), float(curr['gpslong'])
                bearing = get_bearing(lat, lon, float(nxt['gpslati']), float(nxt['gpslong'])) if nxt else 0
                
                html = f"""<div style="position:relative; width:40px; height:40px;">
                    <div style="position:absolute; left:14px; top:14px; width:14px; height:14px; background:{get_color_by_bus(b)}; border-radius:50%; border:2px solid white; transform:rotate({bearing}deg); color:white; font-size:10px; display:flex; align-items:center; justify-content:center;">&uarr;</div>
                    <div style="position:absolute; bottom:30px; left:50%; transform:translateX(-50%); background:white; border:1px solid {get_color_by_bus(b)}; padding:2px 4px; font-size:11px; font-weight:bold; white-space:nowrap;">{b} {status['curr']}</div>
                </div>"""
                folium.Marker([lat, lon], icon=folium.DivIcon(html=html)).add_to(m)
                
                eta = get_arrival_info(next((n['nodeid'] for n in nodes if n['nodenm'] == ref_name), ""), b, API_KEY, CITY_CODE) if ref_name != "선택 안함" else None
                dist = get_target_info(nodes, status['ord'], ref_name, bus_db)
                st.write(f"**{b}번** {eta if eta else dist} | {status['curr']} → {nxt['nodenm'] if nxt else '종점'}")
                st.markdown("---")
        st_folium(m, width="100%", height=400)
elif mode == "경유 버스 목록": st.write(f"{ref_name} 경유: {', '.join(find_buses_at_node(bus_db, ref_name))}")
elif mode == "노선 순서 보기":
    for b in [b.strip() for b in target_input.split(",")]:
        if b in bus_db:
            with st.expander(f"{b}번 전체 노선 보기"):
                for n in get_sorted_route(list(bus_db[b].values())[0]): st.write(f"{n['nodeord']}. {n['nodenm']}")