import streamlit as st
import pandas as pd
from database_pg import fetch_all, execute
from config import APP_TITLE


# -------------------------------------------------
# AUTO-CREATE Fleet Tables (avoid dashboard errors)
# -------------------------------------------------
def ensure_fleet_tables():
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
        );
        """,
        (),
    )

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
        );
        """,
        (),
    )


# -------------------------------------------------
# Load KPI counts
# -------------------------------------------------
def load_counts():
    # Workers
    rs = fetch_all("SELECT COUNT(*) AS c FROM workers WHERE status='Active'")
    workers_active = rs[0]["c"] if rs else 0

    # Work orders
    rs = fetch_all("SELECT status FROM work_orders")
    df = pd.DataFrame(rs) if rs else pd.DataFrame(columns=["status"])
    open_wo = (df["status"].isin(["Open", "In Progress"])).sum()
    closed_wo = (df["status"].isin(["Completed", "Closed"])).sum()

    # Attendance today
    today_rs = fetch_all(
        "SELECT status FROM attendance WHERE att_date = CURRENT_DATE"
    )
    df_att = pd.DataFrame(today_rs) if today_rs else pd.DataFrame(columns=["status"])
    present = (df_att["status"] == "Present").sum()
    absent = (df_att["status"] == "Absent").sum()

    return workers_active, open_wo, closed_wo, present, absent


# -------------------------------------------------
# Attendance Trend (last N days)
# -------------------------------------------------
def load_attendance_trend(days=14):
    rows = fetch_all(
        """
        SELECT att_date, status
        FROM attendance
        WHERE att_date >= CURRENT_DATE - %s::int
        ORDER BY att_date
        """,
        (days,),
    )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["att_date"] = pd.to_datetime(df["att_date"])
    df = df[df["status"].isin(["Present", "Absent"])]

    return (
        df.groupby(["att_date", "status"])
        .size()
        .reset_index(name="count")
    )


# -------------------------------------------------
# Work Order Status Summary
# -------------------------------------------------
def load_wo_status():
    rows = fetch_all("SELECT status FROM work_orders")
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["status"])


# -------------------------------------------------
# Fleet Summary (last 30 days)
# -------------------------------------------------
def load_fleet_summary(days=30):
    ensure_fleet_tables()

    rows = fetch_all(
        """
        SELECT v.name AS vehicle_name,
               f.hours_used,
               f.total_cost
        FROM fleet_timesheet f
        LEFT JOIN fleet_vehicles v ON f.vehicle_id = v.id
        WHERE f.used_date >= CURRENT_DATE - %s::int
        """,
        (days,),
    )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df["hours_used"] = pd.to_numeric(df["hours_used"], errors="coerce").fillna(0.0)
    df["total_cost"] = pd.to_numeric(df["total_cost"], errors="coerce").fillna(0.0)

    return df


# -------------------------------------------------
# Helper for bar charts
# -------------------------------------------------
def plot_bar(df, x, y, title, x_label, y_label):
    import plotly.express as px

    fig = px.bar(df, x=x, y=y, title=title)
    fig.update_layout(xaxis_title=x_label, yaxis_title=y_label)
    return fig


# -------------------------------------------------
# MAIN RENDER FUNCTION
# -------------------------------------------------
def render():
    st.title("📊 Facility Management Dashboard")
    st.caption(APP_TITLE)

    # KPI Tiles
    workers_active, open_wo, closed_wo, present, _absent = load_counts()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Active Workers", workers_active)
    k2.metric("Open WOs", open_wo)
    k3.metric("Closed WOs", closed_wo)
    k4.metric("Present Today", present)

    st.markdown("---")

    # Try to import Plotly
    try:
        import plotly.express as px
    except:
        st.error("Plotly missing: pip install plotly")
        return

    left, right = st.columns(2)

    # Work Order Status Chart
    with left:
        st.subheader("🛠 Work Orders by Status")

        df_wo = load_wo_status()
        if df_wo.empty:
            st.info("No Work Orders yet.")
        else:
            status_counts = (
                df_wo.groupby("status")
                .size()
                .reset_index(name="count")
            )

            fig = px.pie(status_counts, names="status", values="count", title="WO Status")
            st.plotly_chart(fig, width="stretch")

    # Attendance Trend Chart
    with right:
        st.subheader("🕒 Attendance Trend (Last 14 Days)")

        df_trend = load_attendance_trend(14)
        if df_trend.empty:
            st.info("No attendance data.")
        else:
            fig2 = px.line(
                df_trend,
                x="att_date",
                y="count",
                color="status",
                markers=True,
                title="Attendance Trend",
            )
            st.plotly_chart(fig2, width="stretch")

    st.markdown("---")

    # Fleet Usage Chart
    st.subheader("🚚 Fleet Usage (Last 30 Days)")

    df_fleet = load_fleet_summary(30)
    if df_fleet.empty:
        st.info("No fleet usage data.")
        return

    grp = (
        df_fleet.groupby("vehicle_name", dropna=False)
        .agg(hours=("hours_used", "sum"), cost=("total_cost", "sum"))
        .reset_index()
    )

    c1, c2 = st.columns(2)

    with c1:
        fig_hr = plot_bar(
            grp.sort_values("hours", ascending=False),
            "vehicle_name",
            "hours",
            "Hours by Vehicle",
            "Vehicle",
            "Hours",
        )
        st.plotly_chart(fig_hr, width="stretch")

    with c2:
        fig_cost = plot_bar(
            grp.sort_values("cost", ascending=False),
            "vehicle_name",
            "cost",
            "Cost by Vehicle",
            "Vehicle",
            "Cost (IQD)",
        )
        st.plotly_chart(fig_cost, width="stretch")
