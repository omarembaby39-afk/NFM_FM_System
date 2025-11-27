import streamlit as st
import pandas as pd
from datetime import date

from database_pg import fetch_all


def _load_work_orders(start_date, end_date):
    rows = fetch_all(
        """
        SELECT
            wo.id,
            wo.wo_number,
            wo.status,
            wo.priority,
            wo.requested_at,
            wo.target_date,
            wo.closed_at,
            b.name AS building_name,
            wc.name AS wc_group_name
        FROM work_orders wo
        LEFT JOIN buildings b ON wo.building_id = b.id
        LEFT JOIN wc_groups wc ON wo.wc_group_id = wc.id
        WHERE wo.requested_at::date BETWEEN %s AND %s
        ORDER BY wo.requested_at DESC
        """,
        (start_date, end_date),
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _prepare_sla_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    if df_raw.empty:
        return df_raw

    df = df_raw.copy()

    # Ensure datetime types
    df["requested_at"] = pd.to_datetime(df["requested_at"])
    df["target_date"] = pd.to_datetime(df["target_date"], errors="coerce")
    df["closed_at"] = pd.to_datetime(df["closed_at"], errors="coerce")

    # Simple fix duration (only for closed WOs)
    df["fix_hours"] = (
        (df["closed_at"] - df["requested_at"]).dt.total_seconds() / 3600.0
    )
    df["fix_hours"] = df["fix_hours"].fillna(0.0).astype(float)

    today = date.today()

    # Dates only for SLA calculations
    df["req_date"] = df["requested_at"].dt.date
    df["tgt_date"] = df["target_date"].dt.date
    df["cls_date"] = df["closed_at"].dt.date

    # Overdue = still open/in progress AND target date passed
    df["is_overdue"] = (
        df["status"].isin(["Open", "In Progress"])
        & df["target_date"].notna()
        & (df["tgt_date"] < today)
    )

    # SLA evaluation only when target_date is set and WO is closed
    sla_df = df[df["target_date"].notna() & df["status"].isin(["Completed", "Closed"])].copy()

    sla_df["sla_met"] = sla_df["cls_date"] <= sla_df["tgt_date"]
    sla_df["sla_miss"] = sla_df["cls_date"] > sla_df["tgt_date"]

    # Attach back aggregated SLA to main df by id (optional)
    df = df.merge(
        sla_df[["id", "sla_met", "sla_miss"]],
        on="id",
        how="left",
        suffixes=("", "_sla"),
    )

    df["sla_met"] = df["sla_met"].fillna(False)
    df["sla_miss"] = df["sla_miss"].fillna(False)

    return df


def render():
    st.title("⏱ SLA Dashboard – Work Orders")

    st.caption(
        "SLA view for Work Orders at Um Qasr Welcome Yard: "
        "open vs closed vs overdue, SLA compliance and fix times."
    )

    # --------------------------------------------
    # Date range selector (by requested_at)
    # --------------------------------------------
    today = date.today()
    default_start = today.replace(day=1)
    default_end = today

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From Date (Requested At)", value=default_start, key="sla_start")
    with col2:
        end_date = st.date_input("To Date (Requested At)", value=default_end, key="sla_end")

    if start_date > end_date:
        st.error("Start date cannot be after End date.")
        return

    # --------------------------------------------
    # Load data
    # --------------------------------------------
    with st.spinner("Loading work orders from Neon..."):
        df_raw = _load_work_orders(start_date, end_date)

    if df_raw.empty:
        st.info("No work orders in this period.")
        return

    df = _prepare_sla_df(df_raw)

    # Optional filter by building
    buildings = ["(All)"] + sorted(
        [b for b in df["building_name"].dropna().unique().tolist() if b]
    )
    sel_building = st.selectbox("Filter by Building", buildings, key="sla_building_filter")
    if sel_building != "(All)":
        df = df[df["building_name"] == sel_building]

    # --------------------------------------------
    # Summary metrics
    # --------------------------------------------
    st.markdown("### 🔎 SLA Summary")

    total_wo = len(df)
    open_wo = (df["status"].isin(["Open", "In Progress"])).sum()
    closed_wo = (df["status"].isin(["Completed", "Closed"])).sum()
    overdue_wo = df["is_overdue"].sum()

    sla_met_count = df["sla_met"].sum()
    sla_miss_count = df["sla_miss"].sum()
    sla_denom = sla_met_count + sla_miss_count
    if sla_denom > 0:
        sla_rate = sla_met_count / sla_denom * 100.0
    else:
        sla_rate = 0.0

    avg_fix_hours = df.loc[df["fix_hours"] > 0, "fix_hours"].mean()
    if pd.isna(avg_fix_hours):
        avg_fix_hours = 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total WOs", total_wo)
    c2.metric("Open / In Progress", int(open_wo))
    c3.metric("Closed", int(closed_wo))
    c4.metric("Overdue", int(overdue_wo))

    c5, c6 = st.columns(2)
    c5.metric("SLA Compliance", f"{sla_rate:.1f}%")
    c6.metric("Avg Fix Time", f"{avg_fix_hours:.1f} h")

    st.markdown("---")

    # --------------------------------------------
    # Charts
    # --------------------------------------------
    try:
        import plotly.express as px
    except ImportError:
        st.warning("Plotly is not installed. Run: pip install plotly")
        return

    # Status distribution
    st.markdown("### 📊 Work Orders by Status")

    status_counts = (
        df.groupby("status")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    fig_status = px.pie(
        status_counts,
        names="status",
        values="count",
        title="Work Orders by Status",
    )
    st.plotly_chart(fig_status, use_container_width=True)

    # SLA by priority
    st.markdown("### 🧯 SLA Compliance by Priority")

    sla_by_priority = (
        df[df["sla_met"] | df["sla_miss"]]
        .groupby("priority")
        .agg(
            sla_met=("sla_met", "sum"),
            sla_miss=("sla_miss", "sum"),
        )
        .reset_index()
    )

    if not sla_by_priority.empty:
        sla_by_priority["total"] = sla_by_priority["sla_met"] + sla_by_priority["sla_miss"]
        sla_by_priority["sla_pct"] = (
            sla_by_priority["sla_met"] / sla_by_priority["total"] * 100.0
        )

        fig_prio = px.bar(
            sla_by_priority,
            x="priority",
            y="sla_pct",
            text="sla_pct",
            title="SLA Compliance by Priority",
        )
        fig_prio.update_layout(yaxis_title="SLA %", xaxis_title="Priority")
        st.plotly_chart(fig_prio, use_container_width=True)
    else:
        st.info("No closed WOs with target dates to compute SLA by priority.")

    # Overdue by building
    st.markdown("### 🏢 Overdue WOs by Building")

    overdue_df = df[df["is_overdue"]]
    if not overdue_df.empty:
        overdue_by_building = (
            overdue_df.groupby("building_name")
            .size()
            .reset_index(name="overdue_count")
            .sort_values("overdue_count", ascending=False)
        )
        fig_overdue = px.bar(
            overdue_by_building,
            x="building_name",
            y="overdue_count",
            title="Overdue Work Orders by Building",
        )
        fig_overdue.update_layout(
            xaxis_title="Building",
            yaxis_title="Overdue WOs",
        )
        st.plotly_chart(fig_overdue, use_container_width=True)
    else:
        st.info("No overdue WOs in this period.")

    st.markdown("---")

    # --------------------------------------------
    # Detailed table + export
    # --------------------------------------------
    st.markdown("### 🧾 SLA Detail Table")

    show_cols = [
        "wo_number",
        "status",
        "priority",
        "building_name",
        "wc_group_name",
        "requested_at",
        "target_date",
        "closed_at",
        "is_overdue",
        "sla_met",
        "sla_miss",
        "fix_hours",
    ]
    show_cols = [c for c in show_cols if c in df.columns]

    st.dataframe(df[show_cols], use_container_width=True)

    csv_data = df[show_cols].to_csv(index=False).encode("utf-8")
    file_name = f"sla_workorders_{start_date}_{end_date}.csv"

    st.download_button(
        "⬇ Download SLA Data (CSV)",
        data=csv_data,
        file_name=file_name,
        mime="text/csv",
    )
