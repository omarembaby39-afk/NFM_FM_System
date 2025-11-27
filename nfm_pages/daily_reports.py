import streamlit as st
import pandas as pd
from datetime import date
from database_pg import fetch_all, execute


def render():
    st.title("📝 Daily Reports – Um Qasr FM")

    st.caption(
        "Record daily status for WC groups, buildings, and work orders. "
        "Data is stored in Neon PostgreSQL."
    )

    st.markdown("---")

    # -------------------------------------------------
    # Load support data (buildings, WC groups, WOs)
    # -------------------------------------------------
    b_rows = fetch_all("SELECT id, code, name FROM buildings ORDER BY code ASC")
    wc_rows = fetch_all("SELECT id, code, name FROM wc_groups ORDER BY code ASC")
    wo_rows = fetch_all("SELECT id, wo_number, title FROM work_orders ORDER BY id DESC")

    df_b = pd.DataFrame(b_rows)
    df_wc = pd.DataFrame(wc_rows)
    df_wo = pd.DataFrame(wo_rows)

    # Build selection lists
    b_options = ["(None)"]
    b_map = {}
    if not df_b.empty:
        for _, r in df_b.iterrows():
            label = f"{r['code']} – {r['name']}"
            b_options.append(label)
            b_map[label] = r["id"]

    wc_options = ["(None)"]
    wc_map = {}
    if not df_wc.empty:
        for _, r in df_wc.iterrows():
            label = f"{r['code']} – {r['name']}"
            wc_options.append(label)
            wc_map[label] = r["id"]

    wo_options = ["(None)"]
    wo_map = {}
    if not df_wo.empty:
        for _, r in df_wo.iterrows():
            label = f"{r['wo_number']} – {r['title']}"
            wo_options.append(label)
            wo_map[label] = r["id"]

    # -------------------------------------------------
    # Form: Add new daily report
    # -------------------------------------------------
    st.subheader("Add New Daily Report")

    col1, col2 = st.columns(2)

    with col1:
        rep_date = st.date_input("Report Date", value=date.today())
        rep_type = st.selectbox(
            "Report Type", ["WC", "Building", "General", "Fleet", "Other"], index=0
        )
        status = st.selectbox("Status", ["Normal", "Issue", "Critical"], index=0)

    with col2:
        wc_sel = st.selectbox("Related WC Group", wc_options, index=0)
        b_sel = st.selectbox("Related Building", b_options, index=0)
        wo_sel = st.selectbox("Related Work Order", wo_options, index=0)

    summary = st.text_area("Summary", placeholder="Short description of today's status", height=80)
    notes = st.text_area("Detailed Notes", placeholder="More details if needed", height=100)

    if st.button("Save Daily Report", type="primary"):
        wc_id = wc_map.get(wc_sel) if wc_sel != "(None)" else None
        b_id = b_map.get(b_sel) if b_sel != "(None)" else None
        wo_id = wo_map.get(wo_sel) if wo_sel != "(None)" else None

        if not summary:
            st.error("Summary is required.")
        else:
            ok = execute(
                """
                INSERT INTO daily_reports
                (report_date, report_type, status,
                 wc_group_id, building_id, work_order_id,
                 summary, notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (rep_date, rep_type, status, wc_id, b_id, wo_id, summary.strip(), notes.strip()),
            )
            if ok:
                st.success("Daily report saved successfully.")
            else:
                st.error("Failed to save daily report. Check Neon connection.")

    st.markdown("---")

    # -------------------------------------------------
    # List recent daily reports
    # -------------------------------------------------
    st.subheader("Recent Daily Reports")

    rows = fetch_all(
        """
        SELECT dr.*, 
               b.code AS building_code,
               b.name AS building_name,
               wc.code AS wc_code,
               wc.name AS wc_name,
               wo.wo_number
        FROM daily_reports dr
        LEFT JOIN buildings b ON dr.building_id = b.id
        LEFT JOIN wc_groups wc ON dr.wc_group_id = wc.id
        LEFT JOIN work_orders wo ON dr.work_order_id = wo.id
        ORDER BY dr.report_date DESC, dr.id DESC
        LIMIT 200
        """
    )

    if not rows:
        st.info("No daily reports recorded yet.")
        return

    df = pd.DataFrame(rows)

    # Filters
    colf1, colf2, colf3 = st.columns(3)
    with colf1:
        type_filter = st.selectbox(
            "Filter by Type", ["(All)", "WC", "Building", "General", "Fleet", "Other"], index=0
        )
    with colf2:
        status_filter = st.selectbox(
            "Filter by Status", ["(All)", "Normal", "Issue", "Critical"], index=0
        )
    with colf3:
        show_only_with_wo = st.checkbox("Only reports linked to a Work Order")

    df_view = df.copy()

    if type_filter != "(All)":
        df_view = df_view[df_view["report_type"] == type_filter]

    if status_filter != "(All)":
        df_view = df_view[df_view["status"] == status_filter]

    if show_only_with_wo:
        df_view = df_view[~df_view["work_order_id"].isna()]

    # Build nice display columns
    def build_location(row):
        parts = []
        if row.get("building_code"):
            parts.append(f"B: {row['building_code']}")
        if row.get("wc_code"):
            parts.append(f"WC: {row['wc_code']}")
        return " | ".join(parts)

    df_view["Location"] = df_view.apply(build_location, axis=1)
    df_view["WO"] = df_view["wo_number"].fillna("")

    cols_show = [
        "id",
        "report_date",
        "report_type",
        "status",
        "Location",
        "WO",
        "summary",
        "notes",
    ]
    cols_show = [c for c in cols_show if c in df_view.columns]

    st.dataframe(df_view[cols_show], use_container_width=True)
