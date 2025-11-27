import streamlit as st
import pandas as pd
from datetime import date

from database_pg import fetch_all


def _load_attendance(start_date, end_date):
    rows = fetch_all(
        """
        SELECT
            w.id AS worker_id,
            w.worker_code,
            w.full_name,
            w.position,
            w.status,
            w.salary,
            a.att_date,
            a.status AS att_status,
            a.hours_worked,
            a.overtime_hours
        FROM workers w
        LEFT JOIN attendance a
            ON w.id = a.worker_id
           AND a.att_date BETWEEN %s AND %s
        WHERE w.status = 'Active'
        ORDER BY w.worker_code, a.att_date
        """,
        (start_date, end_date),
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_work_orders(start_date, end_date):
    rows = fetch_all(
        """
        SELECT
            assigned_worker_id AS worker_id,
            status
        FROM work_orders
        WHERE assigned_worker_id IS NOT NULL
          AND requested_at::date BETWEEN %s AND %s
        """,
        (start_date, end_date),
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_fleet(start_date, end_date):
    rows = fetch_all(
        """
        SELECT
            worker_id,
            hours_used
        FROM fleet_timesheet
        WHERE worker_id IS NOT NULL
          AND used_date BETWEEN %s AND %s
        """,
        (start_date, end_date),
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _build_kpi_df(start_date, end_date):
    df_att = _load_attendance(start_date, end_date)
    df_wo = _load_work_orders(start_date, end_date)
    df_fleet = _load_fleet(start_date, end_date)

    if df_att.empty:
        return pd.DataFrame()

    # -----------------------------
    # Attendance KPIs
    # -----------------------------
    grp = df_att.groupby(
        ["worker_id", "worker_code", "full_name", "position", "salary"],
        dropna=False,
    )

    agg = grp.agg(
        days_recorded=("att_date", "nunique"),
        days_present=("att_status", lambda x: (x == "Present").sum()),
        days_absent=("att_status", lambda x: (x == "Absent").sum()),
        days_leave=("att_status", lambda x: (x == "Leave").sum()),
        total_hours=("hours_worked", "sum"),
        total_ot=("overtime_hours", "sum"),
    ).reset_index()

    # Fill NaN with 0
    num_cols = [
        "days_recorded",
        "days_present",
        "days_absent",
        "days_leave",
        "total_hours",
        "total_ot",
    ]
    agg[num_cols] = agg[num_cols].fillna(0)

    # Ensure numeric types are float (avoid Decimal issues)
    for col in ["total_hours", "total_ot"]:
        agg[col] = agg[col].astype(float)

    # Attendance %
    def calc_attendance_rate(row):
        denom = row["days_present"] + row["days_absent"]
        if denom <= 0:
            return 0.0
        return float(row["days_present"]) / float(denom) * 100.0

    agg["attendance_pct"] = agg.apply(calc_attendance_rate, axis=1)

    # -----------------------------
    # Work Order KPIs
    # -----------------------------
    if not df_wo.empty:
        wo_grp = df_wo.groupby("worker_id", dropna=True).agg(
            wo_total=("status", "count"),
            wo_closed=("status", lambda x: x.isin(["Completed", "Closed"]).sum()),
        )
        agg = agg.merge(
            wo_grp,
            left_on="worker_id",
            right_index=True,
            how="left",
        )
    else:
        agg["wo_total"] = 0
        agg["wo_closed"] = 0

    agg[["wo_total", "wo_closed"]] = agg[["wo_total", "wo_closed"]].fillna(0)

    def calc_wo_close_rate(row):
        if row["wo_total"] <= 0:
            return 0.0
        return float(row["wo_closed"]) / float(row["wo_total"]) * 100.0

    agg["wo_close_pct"] = agg.apply(calc_wo_close_rate, axis=1)

    # -----------------------------
    # Fleet KPIs
    # -----------------------------
    if not df_fleet.empty:
        fl_grp = df_fleet.groupby("worker_id", dropna=True).agg(
            fleet_hours=("hours_used", "sum"),
        )
        agg = agg.merge(
            fl_grp,
            left_on="worker_id",
            right_index=True,
            how="left",
        )
    else:
        agg["fleet_hours"] = 0.0

    agg["fleet_hours"] = agg["fleet_hours"].fillna(0.0).astype(float)

    # -----------------------------
    # KPI Scoring (0–100)
    # -----------------------------
    def calc_scores(row):
        # force everything to float
        att_score = float(row.get("attendance_pct") or 0.0)

        ot_val = float(row.get("total_ot") or 0.0)
        if ot_val > 0:
            ot_score = min(ot_val, 40.0) / 40.0 * 100.0
        else:
            ot_score = 0.0

        wo_score = float(row.get("wo_close_pct") or 0.0)

        fleet_val = float(row.get("fleet_hours") or 0.0)
        if fleet_val > 0:
            fleet_score = min(fleet_val, 60.0) / 60.0 * 100.0
        else:
            fleet_score = 0.0

        # Clamp scores between 0–100
        att_score = max(0.0, min(100.0, att_score))
        ot_score = max(0.0, min(100.0, ot_score))
        wo_score = max(0.0, min(100.0, wo_score))
        fleet_score = max(0.0, min(100.0, fleet_score))

        # Weights: Attendance 40%, OT 20%, WO 20%, Fleet 20%
        kpi = att_score * 0.4 + ot_score * 0.2 + wo_score * 0.2 + fleet_score * 0.2
        return att_score, ot_score, wo_score, fleet_score, round(kpi, 1)

    scores = agg.apply(calc_scores, axis=1, result_type="expand")
    scores.columns = ["att_score", "ot_score", "wo_score", "fleet_score", "kpi_score"]

    agg = pd.concat([agg, scores], axis=1)

    # Sort by KPI descending
    agg = agg.sort_values("kpi_score", ascending=False).reset_index(drop=True)

    return agg


def render():
    st.title("📊 Worker KPI Dashboard – NFM Um Qasr")

    st.caption(
        "KPIs based on attendance, overtime, work orders and fleet operation. "
        "This helps you track best performers and low performers per period."
    )

    # --------------------------------------------
    # Date range selector
    # --------------------------------------------
    today = date.today()
    default_start = today.replace(day=1)
    default_end = today

    cold1, cold2 = st.columns(2)
    with cold1:
        start_date = st.date_input("From Date", value=default_start, key="kpi_start")
    with cold2:
        end_date = st.date_input("To Date", value=default_end, key="kpi_end")

    if start_date > end_date:
        st.error("Start date cannot be after End date.")
        return

    # --------------------------------------------
    # Load KPI dataframe
    # --------------------------------------------
    with st.spinner("Calculating KPIs from Neon..."):
        df_kpi = _build_kpi_df(start_date, end_date)

    if df_kpi.empty:
        st.info("No KPI data for this period. Check attendance, work orders and fleet tables.")
        return

    # Optional filter by position
    positions = ["(All)"] + sorted(df_kpi["position"].dropna().unique().tolist())
    pos_sel = st.selectbox("Filter by Position", positions, key="kpi_pos_filter")
    df_view = df_kpi.copy()
    if pos_sel != "(All)":
        df_view = df_view[df_view["position"] == pos_sel]

    # --------------------------------------------
    # Global summary
    # --------------------------------------------
    st.markdown("### 🔎 Summary KPIs")

    avg_att = float(df_view["attendance_pct"].mean() or 0.0)
    avg_kpi = float(df_view["kpi_score"].mean() or 0.0)
    total_ot = float(df_view["total_ot"].sum() or 0.0)
    total_fleet = float(df_view["fleet_hours"].sum() or 0.0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg Attendance %", f"{avg_att:.1f}%")
    c2.metric("Avg KPI Score", f"{avg_kpi:.1f} / 100")
    c3.metric("Total OT Hours", f"{total_ot:.1f}")
    c4.metric("Fleet Hours (period)", f"{total_fleet:.1f}")

    st.markdown("---")

    # --------------------------------------------
    # Top & bottom workers
    # --------------------------------------------
    st.markdown("### 🏅 Top 5 Workers (by KPI score)")
    st.dataframe(
        df_view[
            [
                "worker_code",
                "full_name",
                "position",
                "attendance_pct",
                "total_ot",
                "wo_closed",
                "fleet_hours",
                "kpi_score",
            ]
        ]
        .head(5)
        .reset_index(drop=True),
        use_container_width=True,
    )

    st.markdown("### ⚠️ Bottom 5 Workers (by KPI score)")
    st.dataframe(
        df_view[
            [
                "worker_code",
                "full_name",
                "position",
                "attendance_pct",
                "total_ot",
                "wo_closed",
                "fleet_hours",
                "kpi_score",
            ]
        ]
        .tail(5)
        .reset_index(drop=True),
        use_container_width=True,
    )

    st.markdown("---")

    # --------------------------------------------
    # Charts (needs plotly)
    # --------------------------------------------
    try:
        import plotly.express as px
    except ImportError:
        st.warning("Plotly is not installed. Run: pip install plotly")
        return

    st.markdown("### 📈 KPI By Worker")

    fig = px.bar(
        df_view,
        x="worker_code",
        y="kpi_score",
        hover_data=[
            "full_name",
            "position",
            "attendance_pct",
            "total_ot",
            "wo_closed",
            "fleet_hours",
        ],
        title="KPI Score per Worker",
    )
    fig.update_layout(xaxis_title="Worker Code", yaxis_title="KPI Score (0–100)")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ⏱ Attendance vs Overtime (Bubble)")

    fig2 = px.scatter(
        df_view,
        x="attendance_pct",
        y="total_ot",
        size="kpi_score",
        color="position",
        hover_name="full_name",
        title="Attendance % vs OT Hours (bubble size = KPI score)",
    )
    fig2.update_layout(xaxis_title="Attendance %", yaxis_title="OT Hours")
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # --------------------------------------------
    # Detailed table + export
    # --------------------------------------------
    st.markdown("### 🧾 KPI Detail Table")

    show_cols = [
        "worker_code",
        "full_name",
        "position",
        "attendance_pct",
        "days_present",
        "days_absent",
        "days_leave",
        "total_hours",
        "total_ot",
        "wo_total",
        "wo_closed",
        "wo_close_pct",
        "fleet_hours",
        "kpi_score",
    ]
    show_cols = [c for c in show_cols if c in df_view.columns]

    st.dataframe(df_view[show_cols], use_container_width=True)

    csv_data = df_view[show_cols].to_csv(index=False).encode("utf-8")
    file_name = f"worker_kpi_{start_date}_{end_date}.csv"

    st.download_button(
        "⬇ Download KPI Data (CSV)",
        data=csv_data,
        file_name=file_name,
        mime="text/csv",
    )
