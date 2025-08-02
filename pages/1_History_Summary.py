import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from streamlit_autorefresh import st_autorefresh

# ----------------- App Setup -----------------
st.set_page_config(page_title="Energy History Summary", layout="wide")
st_autorefresh(interval=60000, limit=None, key="history_refresh")

st.title("📊 Energy Usage History & Summary")

csv_path = "energy_history.csv"

# Optional: Button to go back to dashboard
if st.button("🏠 Go to Dashboard"):
    st.switch_page("dashboard.py")

# ----------------- Load CSV -----------------
if os.path.exists(csv_path):
    df = pd.read_csv(csv_path)

    # ✅ Handle empty file gracefully
    if df.shape[0] == 0:
        st.warning("⚠️ CSV file exists but contains no data entries yet.")
        st.stop()

    # ✅ Robust datetime parsing
    df['Time'] = pd.to_datetime(df['Time'], errors='coerce')
    df.dropna(subset=['Time'], inplace=True)

    # ✅ Ensure expected columns exist
    expected_cols = ["Time", "Current (mA)", "Voltage (V)", "Power (W)", "Energy (kWh)", "Cost (BDT)", "Duration (min)"]
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        st.error(f"Missing required columns: {missing_cols}")
        st.stop()

    # ----------------- Raw Data -----------------
    st.subheader("Raw Data")
    with st.expander("Show Last 100 Rows"):
        st.dataframe(df.tail(100), use_container_width=True)

    # ----------------- Summary Statistics -----------------
    st.subheader("🔍 Summary Statistics")
    with st.expander("Show Stats"):
        st.write(df.describe())

    # ----------------- Date Filter -----------------
    st.subheader("📆 Filter by Date Range")
    min_date = df["Time"].min().date()
    max_date = df["Time"].max().date()
    start_date, end_date = st.date_input("Select Range", [min_date, max_date], min_value=min_date, max_value=max_date)

    start_datetime = pd.to_datetime(start_date)
    end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    filtered_df = df[(df["Time"] >= start_datetime) & (df["Time"] <= end_datetime)]

    st.caption(f"Filtering data from **{start_datetime}** to **{end_datetime}**")
    st.write(f"✅ Filtered rows: {len(filtered_df)}")

    if not filtered_df.empty:
        # ----------------- Trend: Energy and Cost -----------------
        st.subheader("📈 Energy and Cost Trends")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(filtered_df["Time"], filtered_df["Energy (kWh)"], label="Energy", color="green", linewidth=2)
        ax.plot(filtered_df["Time"], filtered_df["Cost (BDT)"], label="Cost", color="red", linewidth=2)
        ax.set_xlabel("Time")
        ax.set_ylabel("Value")
        ax.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)

        # ----------------- Power over Time -----------------
        st.subheader("⚡ Power vs. Time")
        fig_p, ax_p = plt.subplots(figsize=(10, 5))
        ax_p.plot(filtered_df["Time"], filtered_df["Power (W)"], label="Power", color="blue", linewidth=2)
        ax_p.set_xlabel("Time")
        ax_p.set_ylabel("Power (W)")
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig_p)

        # ----------------- Current vs Voltage -----------------
        st.subheader("🔌 Current vs. Voltage")
        fig_cv, ax_cv = plt.subplots(figsize=(8, 5))
        sns.scatterplot(data=filtered_df, x="Voltage (V)", y="Current (mA)", ax=ax_cv, color="purple")
        ax_cv.set_title("Current vs. Voltage")
        st.pyplot(fig_cv)

        # ----------------- Insights -----------------
        st.subheader("🔍 Insights")

        energy_series = pd.to_numeric(filtered_df["Energy (kWh)"], errors="coerce").dropna()
        cost_series = pd.to_numeric(filtered_df["Cost (BDT)"], errors="coerce").dropna()

        total_energy = energy_series.iloc[-1] - energy_series.iloc[0] if len(energy_series) >= 2 else 0.0
        total_cost = cost_series.iloc[-1] - cost_series.iloc[0] if len(cost_series) >= 2 else 0.0

        st.metric("Max Power", f"{filtered_df['Power (W)'].max():.2f} W")
        st.metric("Total Energy", f"{total_energy:.4f} kWh")
        st.metric("Total Cost", f"৳{total_cost:.2f}")

        # ----------------- Correlation Heatmap -----------------
        st.subheader("📊 Correlation Heatmap")
        fig2, ax2 = plt.subplots()
        sns.heatmap(filtered_df.drop(columns=["Time"]).corr(), annot=True, cmap="coolwarm", ax=ax2)
        st.pyplot(fig2)

        # ----------------- Metric Relationship Plots -----------------
        st.subheader("📊 Explore Metric Relationships")

        plot_options = {
            "Voltage vs Time": ("Time", "Voltage (V)"),
            "Current vs Time": ("Time", "Current (mA)"),
            "Power vs Time": ("Time", "Power (W)"),
            "Energy vs Time": ("Time", "Energy (kWh)"),
            "Cost vs Time": ("Time", "Cost (BDT)"),
            "Voltage vs Current": ("Voltage (V)", "Current (mA)"),
            "Voltage vs Power": ("Voltage (V)", "Power (W)"),
            "Current vs Power": ("Current (mA)", "Power (W)"),
            "Energy vs Cost": ("Energy (kWh)", "Cost (BDT)"),
        }

        selected_plots = st.multiselect(
            "Select metric relationships to visualize:",
            options=list(plot_options.keys()),
            default=["Voltage vs Time", "Current vs Time", "Power vs Time"]
        )

        col1, col2 = st.columns(2)
        col_toggle = True

        for title in selected_plots:
            x, y = plot_options[title]
            fig, ax = plt.subplots(figsize=(6, 4))
            sns.lineplot(data=filtered_df, x=x, y=y, ax=ax, marker="o", linewidth=2)
            ax.set_title(f"{y} vs {x}")
            ax.set_xlabel(x)
            ax.set_ylabel(y)
            ax.grid(True)
            plt.xticks(rotation=45)

            if col_toggle:
                col1.pyplot(fig)
            else:
                col2.pyplot(fig)
            col_toggle = not col_toggle

    else:
        st.warning("⚠️ No data available for the selected date range.")

else:
    st.error("❌ CSV file not found. Please ensure `energy_history.csv` exists in the app directory.")


