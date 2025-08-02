import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import tinytuya
import os
import json
import time
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

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

# ------------------- Session State -------------------
if 'scheduled_off_time' not in st.session_state:
    st.session_state.scheduled_off_time = None
if 'auto_off_active' not in st.session_state:
    st.session_state.auto_off_active = False
if 'history' not in st.session_state:
    st.session_state.history = pd.read_csv(csv_path, parse_dates=['Time']).to_dict('records') if os.path.exists(csv_path) else []
if 'on_time' not in st.session_state:
    st.session_state.on_time = None
if 'duration_minutes' not in st.session_state:
    st.session_state.duration_minutes = 0
if 'last_update_time' not in st.session_state or 'accumulated_kwh' not in st.session_state:
    if os.path.exists(backup_path):
        with open(backup_path) as f:
            saved = json.load(f)
            st.session_state.accumulated_kwh = saved.get("accumulated_kwh", 0.0)
            st.session_state.last_update_time = saved.get("last_update_time", time.time())
    else:
        st.session_state.accumulated_kwh = 0.0
        st.session_state.last_update_time = time.time()

# ------------------- Cloud Functions -------------------
def get_device_status():
    try:
        response = cloud.getstatus(DEVICE_ID)
        dps = {item["code"]: item["value"] for item in response.get("status", [])}
        power_on = dps.get("switch_1", False)
        power = dps.get("cur_power", 0) / 10.0
        voltage = dps.get("cur_voltage", 0) / 10.0
        current = dps.get("cur_current", 0)

        current_time = time.time()
        delta_time_hours = (current_time - st.session_state.last_update_time) / 3600.0
        st.session_state.last_update_time = current_time
        st.session_state.accumulated_kwh += (power / 1000.0) * delta_time_hours
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
        st.warning(f"Error: {e}")
        return False, 0, 0, 0, 0, 0, 0

def toggle_device(state: bool):
    try:
        cloud.sendcommand(DEVICE_ID, [{"code": "switch_1", "value": state}])
        st.success(f"Device turned {'ON' if state else 'OFF'}")
    except Exception as e:
        st.error(f"Error toggling device: {e}")

def schedule_auto_off(hours: float):
    st.session_state.scheduled_off_time = datetime.now() + timedelta(hours=hours)
    st.session_state.auto_off_active = True
    st.success(f"Device will auto turn off at {st.session_state.scheduled_off_time.strftime('%H:%M:%S')}")

def update_history_row():
    now = datetime.now()
    status = get_device_status()
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

# ------------------- UI -------------------
st.set_page_config(page_title="IoT Dashboard | Zinia", layout="wide")
st_autorefresh(interval=60000, limit=None, key="refresh")

st.markdown("""
    <div style="background-color:#1c3d57;padding:20px 20px 5px 20px;border-radius:10px;text-align:center">
        <h2 style="color:white;">⚡ IoT Energy Consumption & Monitoring Dashboard</h2>
    </div>
""", unsafe_allow_html=True)

df, status = update_history_row()
power_on, power, voltage, current_ma, kwh, cost, duration = status

# ------------------- Device Control -------------------
st.subheader("🔌 Device Control")
col_on, col_off, col_status = st.columns([1, 1, 2])
with col_on:
    if st.button("🔋 Turn ON"):
        toggle_device(True)
with col_off:
    if st.button("⛔ Turn OFF"):
        toggle_device(False)
with col_status:
    status_text = "🟢 ON" if power_on else "🔴 OFF"
    st.markdown(f"<div style='text-align:right; color:white; font-weight:bold;'>Device Status: {status_text}</div>", unsafe_allow_html=True)

# ------------------- Auto Turn-Off Scheduler -------------------
st.markdown("---")
st.subheader("⏲️ Auto Turn-Off Scheduler")
col3, col4 = st.columns([2, 3])
with col3:
    hours = st.slider("Set auto turn-off duration (in hours):", 1, 24, 6)
    if not st.session_state.auto_off_active:
        if st.button("Schedule Auto-Off"):
            schedule_auto_off(hours)
    else:
        if st.button("Cancel Auto-Off"):
            st.session_state.scheduled_off_time = None
            st.session_state.auto_off_active = False
            st.info("Auto-off schedule cancelled.")
if st.session_state.scheduled_off_time and datetime.now() >= st.session_state.scheduled_off_time:
    toggle_device(False)
    st.session_state.scheduled_off_time = None
    st.session_state.auto_off_active = False

# ------------------- Gauges -------------------
st.subheader("📟 Real-Time Device Metrics")
c1, c2, c3 = st.columns(3)
with c1:
    st.plotly_chart(build_gauge("Current (mA)", current_ma, 2000), use_container_width=True)
with c2:
    st.plotly_chart(build_gauge("Power (W)", power, 2500), use_container_width=True)
with c3:
    st.plotly_chart(build_gauge("Voltage (V)", voltage, 260), use_container_width=True)
c4, c5, c6 = st.columns(3)
with c4:
    st.plotly_chart(build_gauge("Energy (kWh)", kwh, 10), use_container_width=True)
with c5:
    st.plotly_chart(build_gauge("Total Cost (BDT)", cost, 500), use_container_width=True)
with c6:
    st.plotly_chart(build_gauge("ON Duration (min)", duration, 1440), use_container_width=True)

# ------------------- Donut -------------------
fig_donut = px.pie(
    names=["ON", "OFF"],
    values=[duration, max(1, 1440 - duration)],
    hole=0.5,
    title="Today's Power Usage Distribution",
    color_discrete_sequence=px.colors.qualitative.Set3
)
st.plotly_chart(fig_donut, use_container_width=True)

# ------------------- Trend -------------------
st.subheader("📊 Energy & Cost Over Time")
fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=df['Time'], y=df['Energy (kWh)'], name="Energy (kWh)", mode='lines+markers'))
fig1.add_trace(go.Scatter(x=df['Time'], y=df['Cost (BDT)'], name="Cost (BDT)", mode='lines+markers'))
fig1.update_layout(template="plotly_dark", xaxis_title="Time", yaxis_title="Value")
st.plotly_chart(fig1, use_container_width=True)

st.subheader("📉 Full Metric Trend")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=df['Time'], y=df['Current (mA)'], name="Current"))
fig2.add_trace(go.Scatter(x=df['Time'], y=df['Voltage (V)'], name="Voltage"))
fig2.add_trace(go.Scatter(x=df['Time'], y=df['Power (W)'], name="Power"))
fig2.add_trace(go.Scatter(x=df['Time'], y=df['Energy (kWh)'], name="Energy"))
fig2.add_trace(go.Scatter(x=df['Time'], y=df['Cost (BDT)'], name="Cost"))
fig2.update_layout(template="plotly_dark", xaxis_title="Time", yaxis_title="Values", hovermode="x unified")
st.plotly_chart(fig2, use_container_width=True)

# ------------------- Download -------------------
if st.button("📂 Download CSV History"):
    st.download_button("Download File", df.to_csv(index=False), file_name="energy_history.csv", mime="text/csv")

st.caption("🔧 Developed by Momena Khatun Zinia | Tuya Cloud powered")
