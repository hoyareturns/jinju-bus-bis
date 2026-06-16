import streamlit as st
import urllib.parse
from bus_utils import get_qr_image

BASE_URL = "https://jinju-bus-bis-bpesd99kxyupdbxgsuwvzt.streamlit.app"

def render_sidebar():
    st.sidebar.title("접속 QR")
    current_qr_url = f"{BASE_URL}?buses={urllib.parse.quote(st.session_state['target_bus_input'])}&ref={urllib.parse.quote(st.session_state['selected_node_1'])}"
    st.sidebar.image(get_qr_image(current_qr_url))