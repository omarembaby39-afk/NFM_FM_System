import streamlit as st
import pandas as pd
from datetime import date

from database_pg import fetch_all, execute
from config import FLEET_PHOTO_DIR


def _ensure_tables():
    """Create / migrate fleet tables so queries never fail."""
    # Fleet vehicles table
    execute(
        """
        CREATE TABLE IF NOT EXISTS fleet_vehicles (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            plate_no TEXT,
            hourly_rate NUMERIC(12,2) DEFAULT 0,
            daily_rate NUMERIC(12,2) DEFAULT 0,
            status TEXT DEFAULT 'Active'
        )
        """,
        (),
    )

    # Fleet timesheet table (new structure)
    execute(
        """
        CREATE TABLE IF NOT EXISTS fleet_timesheet (
            id SERIAL PRIMARY KEY,
            vehicle_id INTEGER REFERENCES fleet_vehicles(id) ON DELETE SET NULL,
            worker_id INTEGER REFERENCES workers(id) ON DELETE SET NULL,
            used_date DATE NOT NULL,
            hours_used NUMERIC(10,2) DEFAULT 0,
            km_used NUMERIC(10,2) DEFAULT 0,
            total_cost NUMERIC(14,2) DEFAULT 0,
            notes TEXT
        )
        """,
        (),
    )

    # 🔧 MIGRATION for old tables: add missing columns if needed
    execute(
        "ALTER TABLE fleet_timesheet ADD COLUMN IF NOT EXISTS vehicle_id INTEGER",
        (),
    )
    execute(
        "ALTER TABLE fleet_timesheet ADD COLUMN IF NOT EXISTS worker_id INTEGER",
        (),
    )
    execute(
        "ALTER TABLE fleet_timesheet ADD COLUMN IF NOT EXISTS used_date DATE",
        (),
    )
    execute(
        "ALTER TABLE fleet_timesheet ADD COLUMN IF NOT EXISTS hours_used NUMERIC(10,2)",
        (),
    )
    execute(
        "ALTER TABLE fleet_timesheet ADD COLUMN IF NOT EXISTS km_used NUMERIC(10,2)",
        (),
    )
    execute(
        "ALTER TABLE fleet_timesheet ADD COLUMN IF NOT EXISTS total_cost NUMERIC(14,2)",
        (),
    )
    execute(
        "ALTER TABLE fleet_timesheet ADD COLUMN IF NOT EXISTS notes TEXT",
        (),
    )


def _load_vehicles():
    rows = fetch_all(
        "SELECT id, name, category, plate_no, hourly_rate, daily_rate, status FROM fleet_vehicles ORDER BY name"
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_workers():
    rows = fetch_all(
        "SELECT id, worker_code, full_name, position FROM workers WHERE status='Active' ORDER BY worker_code"
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_timesheet(days=30):
    rows = fetch_all(
        """
        SELECT
            f.id,
            v.name AS vehicle_name,
            f.used_date,
            f.hours_used,
            f.km_used,
            f.total_cost,
            w.worker_code,
            w.full_name
        FROM fleet_timesheet f
        LEFT JOIN fleet_vehicles v ON f.vehicle_id = v.id
        LEFT JOIN workers w ON f.worker_id = w.id
        WHERE f.used_date >= CURRENT_DATE - %s::int
        ORDER BY f.used_date DESC
        """,
        (days,),
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def render():
    st.title("🚚 Fleet & Equipment Management")

    _ensure_tables()

    tab1, tab2, tab3 = st.tabs(["🚜 Vehicles Master", "📋 Usage / Timesheet", "📈 Fleet Analytics"])

    # -----------------------------
    # Tab 1: Vehicles Master
    # -----------------------------
    with tab1:
        st.subheader("🚜 Vehicles & Equipment")

        df_veh = _load_vehicles()
        st.dataframe(df_veh, width="stretch")

        st.markdown("### ➕ Add / Update Vehicle")

        col1, col2, col3 = st.columns(3)
        with col1:
            v_name = st.text_input("Name", key="fleet_v_name")
            v_cat = st.text_input("Category", value="Truck / Sweeper / Tanker", key="fleet_v_cat")
        with col2:
            v_plate = st.text_input("Plate No / ID", key="fleet_v_plate")
            v_hourly = st.number_input("Hourly Rate (IQD)", min_value=0.0, step=1000.0, key="fleet_v_hourly")
        with col3:
            v_daily = st.number_input("Daily Rate (IQD)", min_value=0.0, step=1000.0, key="fleet_v_daily")
            v_status = st.selectbox("Status", ["Active", "Inactive"], key="fleet_v_status")

        if st.button("💾 Add Vehicle", type="primary", key="fleet_v_add_btn"):
            if not v_name.strip():
                st.error("Name is required.")
            else:
                ok = execute(
                    """
                    INSERT INTO fleet_vehicles
                    (name, category, plate_no, hourly_rate, daily_rate, status)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (v_name.strip(), v_cat.strip(), v_plate.strip(), v_hourly, v_daily, v_status),
                )
                if ok:
                    st.success("Vehicle added.")
                    st.rerun()
                else:
                    st.error("❌ Failed to add vehicle.")

    # -----------------------------
    # Tab 2: Usage / Timesheet
    # -----------------------------
    with tab2:
        st.subheader("📋 Record Fleet Usage")

        df_veh = _load_vehicles()
        df_workers = _load_workers()

        if df_veh.empty:
            st.warning("Please add vehicles first in the Vehicles tab.")
        else:
            labels_v = [
                f"{r['name']} ({r['plate_no'] or 'no plate'})"
                for _, r in df_veh.iterrows()
            ]
            map_v = {lbl: r["id"] for lbl, (_, r) in zip(labels_v, df_veh.iterrows())}

            sel_v_label = st.selectbox("Vehicle", labels_v, key="fleet_ts_vehicle")
            vehicle_id = map_v[sel_v_label]

            v_row = df_veh[df_veh["id"] == vehicle_id].iloc[0]
            v_hourly = float(v_row["hourly_rate"] or 0.0)

            used_date = st.date_input("Used Date", value=date.today(), key="fleet_ts_date")

            col_ts1, col_ts2 = st.columns(2)
            with col_ts1:
                hours_used = st.number_input("Hours Used", min_value=0.0, step=0.5, key="fleet_ts_hours")
            with col_ts2:
                km_used = st.number_input("KM Used (optional)", min_value=0.0, step=1.0, key="fleet_ts_km")

            # Assign worker
            worker_id = None
            if not df_workers.empty:
                labels_w = [
                    f"{r['worker_code']} – {r['full_name']}"
                    for _, r in df_workers.iterrows()
                ]
                map_w = {lbl: r["id"] for lbl, (_, r) in zip(labels_w, df_workers.iterrows())}
                sel_w_label = st.selectbox(
                    "Operator (worker) – optional",
                    ["(None)"] + labels_w,
                    key="fleet_ts_worker",
                )
                if sel_w_label != "(None)":
                    worker_id = map_w[sel_w_label]

            notes = st.text_area("Notes (location, task, shift…)", key="fleet_ts_notes")

            total_cost = hours_used * v_hourly

            st.write(f"**Hourly Rate:** {v_hourly:,.0f} IQD")
            st.write(f"**Calculated Cost:** {total_cost:,.0f} IQD")

            if st.button("💾 Save Usage Entry", type="primary", key="fleet_ts_save_btn"):
                ok = execute(
                    """
                    INSERT INTO fleet_timesheet
                    (vehicle_id, worker_id, used_date, hours_used, km_used, total_cost, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (vehicle_id, worker_id, used_date, hours_used, km_used, total_cost, notes),
                )
                if ok:
                    st.success("Usage recorded.")
                    st.rerun()
                else:
                    st.error("❌ Failed to save usage.")

        st.markdown("### Last 30 Days Usage")
        df_ts = _load_timesheet(30)
        st.dataframe(df_ts, width="stretch")

    # -----------------------------
    # Tab 3: Analytics
    # -----------------------------
    with tab3:
        st.subheader("📈 Fleet Analytics (Last 30 days)")

        df_ts = _load_timesheet(30)
        if df_ts.empty:
            st.info("No fleet usage records yet.")
            return

        df_ts["hours_used"] = df_ts["hours_used"].fillna(0).astype(float)
        df_ts["total_cost"] = df_ts["total_cost"].fillna(0).astype(float)

        grp_v = df_ts.groupby("vehicle_name", dropna=False).agg(
            hours=("hours_used", "sum"),
            cost=("total_cost", "sum"),
        ).reset_index()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Hours", f"{grp_v['hours'].sum():.1f}")
        c2.metric("Total Fleet Cost", f"{grp_v['cost'].sum():,.0f} IQD")
        c3.metric("Vehicles Used", grp_v["vehicle_name"].nunique())

        try:
            import plotly.express as px
        except ImportError:
            st.warning("Plotly not installed. Run: pip install plotly")
            return

        col1, col2 = st.columns(2)
        with col1:
            fig1 = px.bar(
                grp_v.sort_values("hours", ascending=False),
                x="vehicle_name",
                y="hours",
                title="Hours per Vehicle",
            )
            st.plotly_chart(fig1, width="stretch")

        with col2:
            fig2 = px.bar(
                grp_v.sort_values("cost", ascending=False),
                x="vehicle_name",
                y="cost",
                title="Cost per Vehicle (IQD)",
            )
            st.plotly_chart(fig2, width="stretch")

        st.markdown("### Raw Timesheet Data")
        st.dataframe(df_ts, width="stretch")
