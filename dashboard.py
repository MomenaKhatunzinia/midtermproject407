import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import tinytuya
import os
import json
import time
from datetime import datetime, timedelta

# ------------------- Theme Toggle -------------------
if "theme" not in st.session_state:
    st.session_state.theme = "Light"

theme = st.sidebar.radio("🌗 Theme", ["Light", "Dark"], index=["Light", "Dark"].index(st.session_state.theme))
st.session_state.theme = theme

css_file = f"styles/{theme.lower()}.css"
if os.path.exists(css_file):
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

plotly_template = "plotly_dark" if theme == "Dark" else "plotly"

# ------------------- Tuya Cloud Setup -------------------
cloud = tinytuya.Cloud(
    apiRegion=st.secrets["API_REGION"],
    apiKey=st.secrets["API_KEY"],
    apiSecret=st.secrets["API_SECRET"],
    apiDeviceID=st.secrets["DEVICE_ID"]
)
DEVICE_ID = st.secrets["DEVICE_ID"]
unit_cost_bdt = 6
csv_path = "energy_history.csv"
backup_path = "session_backup.json"

# ------------------- Session State Init -------------------
defaults = {
    'scheduled_off_time': None,
    'auto_off_active': False,
    'on_time': None,
    'duration_minutes': 0,
    'history': pd.read_csv(csv_path, parse_dates=['Time']).to_dict('records') if os.path.exists(csv_path) else [],
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

if 'last_update_time' not in st.session_state or 'accumulated_kwh' not in st.session_state:
    if os.path.exists(backup_path):
        with open(backup_path) as f:
            saved = json.load(f)
            st.session_state.accumulated_kwh = saved.get("accumulated_kwh", 0.0)
            st.session_state.last_update_time = saved.get("last_update_time", time.time())
    else:
        st.session_state.accumulated_kwh = 0.0
        st.session_state.last_update_time = time.time()

# ------------------- Cached Status -------------------
@st.cache_data(ttl=15)
def get_device_status_cached():
    response = cloud.getstatus(DEVICE_ID)
    dps = {item["code"]: item["value"] for item in response.get("result", [])}
    power_on = dps.get("switch_1", False)
    power = dps.get("cur_power", 0) / 10.0
    voltage = dps.get("cur_voltage", 0) / 10.0
    current = dps.get("cur_current", 0)
    return power_on, power, voltage, current, dps

# ------------------- Device Logic -------------------
def get_device_status():
    try:
        power_on, power, voltage, current, dps = get_device_status_cached()
        now = time.time()
        delta_hours = (now - st.session_state.last_update_time) / 3600.0
        st.session_state.last_update_time = now
        st.session_state.accumulated_kwh += (power / 1000.0) * delta_hours
        cost = st.session_state.accumulated_kwh * unit_cost_bdt

        if power_on:
            if not st.session_state.on_time:
                st.session_state.on_time = datetime.now()
            st.session_state.duration_minutes = int((datetime.now() - st.session_state.on_time).total_seconds() / 60)
        else:
            st.session_state.on_time = None
            st.session_state.duration_minutes = 0

        return power_on, power, voltage, current, st.session_state.accumulated_kwh, cost, st.session_state.duration_minutes
    except Exception as e:
        st.warning(f"Error fetching status: {e}")
        return False, 0, 0, 0, 0, 0, 0

def toggle_device(state: bool):
    try:
        cloud.sendcommand(DEVICE_ID, [{"code": "switch_1", "value": state}])
        st.success(f"Device turned {'ON' if state else 'OFF'}")
    except Exception as e:
        st.error(f"Error: {e}")

def schedule_auto_off(hours: float):
    st.session_state.scheduled_off_time = datetime.now() + timedelta(hours=hours)
    st.session_state.auto_off_active = True
    st.success(f"Auto-off scheduled at {st.session_state.scheduled_off_time.strftime('%H:%M:%S')}")

def update_history_row():
    now = datetime.now()
    if 'last_log_time' not in st.session_state or len(st.session_state.history) == 0:
        st.session_state.last_log_time = time.time() - 61

    if time.time() - st.session_state.last_log_time < 60:
        status = get_device_status()
        return pd.DataFrame(st.session_state.history), status

    status = get_device_status()
    st.session_state.last_log_time = time.time()
    record = {
        "Time": now,
        "Current (mA)": status[3],
        "Voltage (V)": status[2],
        "Power (W)": status[1],
        "Energy (kWh)": status[4],
        "Cost (BDT)": status[5],
        "Duration (min)": status[6]
    }
    st.session_state.history.append(record)
    df = pd.DataFrame(st.session_state.history)
    df.to_csv(csv_path, index=False)
    with open(backup_path, "w") as f:
        json.dump({
            "accumulated_kwh": st.session_state.accumulated_kwh,
            "last_update_time": st.session_state.last_update_time
        }, f)
    return df, status

def build_gauge(label, value, max_value):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': label},
        gauge={'axis': {'range': [0, max_value]}, 'bar': {'color': "lightblue"}}
    ))
    fig.update_layout(margin=dict(t=10, b=0, l=0, r=0))
    return fig

# ------------------- UI Layout -------------------
st.set_page_config(page_title="IoT Dashboard | Zinia", layout="wide")

st.markdown("""
    <div style="background-color:#1c3d57;padding:20px 20px 5px 20px;border-radius:10px;text-align:center">
        <h2 style="color:white;">⚡ IoT Energy Consumption & Monitoring Dashboard</h2>
    </div>
""", unsafe_allow_html=True)

st.button("🔁 Refresh Status", on_click=st.rerun)

with st.spinner("Loading device data..."):
    df, status = update_history_row()
    power_on, power, voltage, current_ma, kwh, cost, duration = status

# ------------------- Device Control Section -------------------
st.subheader("🔌 Device Control")
col1, col2, col3 = st.columns(3)
if col1.button("🔴 Turn OFF"):
    toggle_device(False)
if col2.button("🟢 Turn ON"):
    toggle_device(True)
if col3.button("⏰ Auto-Off in 1 Hour"):
    schedule_auto_off(1.0)

# Auto-Off Countdown
if st.session_state.auto_off_active:
    time_left = st.session_state.scheduled_off_time - datetime.now()
    if time_left.total_seconds() <= 0:
        toggle_device(False)
        st.session_state.auto_off_active = False
        st.success("✅ Auto-off executed.")
    else:
        st.info(f"⏳ Auto-off in {str(time_left).split('.')[0]}")

# ------------------- Metrics -------------------
st.subheader("📟 Real-Time Metrics")
m1, m2, m3 = st.columns(3)
m1.metric("Power (W)", f"{power:.1f}")
m2.metric("Voltage (V)", f"{voltage:.1f}")
m3.metric("Current (mA)", f"{current_ma:.1f}")

# Gauges
g1, g2, g3 = st.columns(3)
g1.plotly_chart(build_gauge("Power (W)", power, 3000), use_container_width=True)
g2.plotly_chart(build_gauge("Voltage (V)", voltage, 250), use_container_width=True)
g3.plotly_chart(build_gauge("Current (mA)", current_ma, 15000), use_container_width=True)

# ------------------- Summary -------------------
st.subheader("📊 Energy Summary")
st.info(f"**Total Energy Used:** {kwh:.4f} kWh")
st.info(f"**Estimated Cost:** ৳{cost:.2f}")
st.info(f"**Active Duration:** {duration} min")

# ------------------- History Charts -------------------
if df.empty:
    st.warning("No energy history data yet. Please wait 1 minute.")
else:
    st.subheader("📈 Historical Trends")

    charts = {
        "Power (W)": "Power (W)",
        "Voltage (V)": "Voltage (V)",
        "Current (mA)": "Current (mA)",
        "Energy (kWh)": "Energy (kWh)",
        "Cost (BDT)": "Cost (BDT)"
    }

    for title, column in charts.items():
        fig = px.line(df, x="Time", y=column, title=title + " Over Time", template=plotly_template)
        st.plotly_chart(fig, use_container_width=True)
