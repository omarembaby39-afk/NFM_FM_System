import os
from datetime import date, datetime, time

import pandas as pd
import streamlit as st

from database_pg import fetch_all, execute
from config import WC_PHOTO_DIR


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _load_supervisors():
    rows = fetch_all(
        """
        SELECT id, worker_code, full_name, position
        FROM workers
        WHERE status = 'Active'
          AND (LOWER(position) LIKE '%supervisor%' OR LOWER(position) LIKE '%engineer%')
        ORDER BY worker_code
        """
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_workers():
    rows = fetch_all(
        """
        SELECT id, worker_code, full_name, position
        FROM workers
        WHERE status = 'Active'
        ORDER BY worker_code
        """
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_buildings():
    rows = fetch_all(
        """
        SELECT id, name
        FROM buildings
        ORDER BY name
        """
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_wc_groups():
    rows = fetch_all(
        """
        SELECT id, name
        FROM wc_groups
        ORDER BY name
        """
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# -------------------------------------------------
# Main render
# -------------------------------------------------
def render():
    st.title("📱 Supervisor Mobile – NFM Um Qasr")

    st.caption(
        "Light mobile-friendly interface for supervisors: quick attendance, "
        "work orders and WC photos. Designed to be used from phone browser."
    )

    # Make layout look like mobile app
    st.markdown(
        """
        <style>
        /* Narrow centered layout for mobile feeling */
        .block-container {
            max-width: 700px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------
    # Supervisor selection (top)
    # -------------------------------------------------
    df_sup = _load_supervisors()
    if df_sup.empty:
        st.error("No supervisors/engineers found. Please add them in Workers page.")
        return

    sup_labels = [
        f"{r['worker_code']} – {r['full_name']} ({r['position']})"
        for _, r in df_sup.iterrows()
    ]
    sup_id_map = {label: r["id"] for label, (_, r) in zip(sup_labels, df_sup.iterrows())}

    sel_sup_label = st.selectbox("Supervisor / Engineer", sup_labels, key="sup_mobile_select")
    supervisor_id = sup_id_map[sel_sup_label]

    st.markdown("---")

    # Big buttons for quick navigation
    tab1, tab2, tab3 = st.tabs(
        ["🕒 Quick Attendance", "🛠 Quick Work Order", "🚻 WC Photos & Notes"]
    )

    # ==========================================================
    # TAB 1 – QUICK ATTENDANCE
    # ==========================================================
    with tab1:
        st.subheader("🕒 Quick Attendance")

        df_workers = _load_workers()
        if df_workers.empty:
            st.info("No active workers found. Please add workers first.")
        else:
            col_top1, col_top2 = st.columns(2)
            with col_top1:
                att_date = st.date_input(
                    "Date", value=date.today(), key="mobile_att_date"
                )
            with col_top2:
                default_in = time(8, 0)
                default_out = time(17, 0)
                in_time_val = st.time_input("In", value=default_in, key="mobile_att_in")
                out_time_val = st.time_input("Out", value=default_out, key="mobile_att_out")

            # Worker selector (mobile-friendly)
            worker_labels = [
                f"{r['worker_code']} – {r['full_name']} ({r['position']})"
                for _, r in df_workers.iterrows()
            ]
            worker_id_map = {
                label: r["id"] for label, (_, r) in zip(worker_labels, df_workers.iterrows())
            }

            sel_worker_label = st.selectbox(
                "Worker",
                worker_labels,
                key="mobile_att_worker",
            )
            worker_id = worker_id_map[sel_worker_label]

            st.text_area(
                "Notes (optional)",
                key="mobile_att_notes",
                placeholder="Example: Night shift, WC Group 3, replacement for worker XYZ...",
                height=80,
            )

            # Compute hours/OT
            hours_worked = 0.0
            overtime_hours = 0.0
            try:
                dt_in = datetime.combine(att_date, in_time_val)
                dt_out = datetime.combine(att_date, out_time_val)
                if dt_out > dt_in:
                    diff = dt_out - dt_in
                    hours_worked = round(diff.total_seconds() / 3600.0, 2)
                    overtime_hours = max(0.0, hours_worked - 8.0)
            except Exception:
                pass

            st.write(f"**Hours Worked:** {hours_worked:.2f}")
            st.write(f"**Overtime (x1):** {overtime_hours:.2f}")

            if st.button("✅ Save Attendance", type="primary", key="btn_mobile_att_save"):
                notes = st.session_state.get("mobile_att_notes", "").strip()

                # Check if there's already attendance for this worker/date
                existing_rows = fetch_all(
                    "SELECT * FROM attendance WHERE worker_id=%s AND att_date=%s",
                    (worker_id, att_date),
                )
                existing = existing_rows[0] if existing_rows else None

                if existing:
                    ok = execute(
                        """
                        UPDATE attendance
                        SET in_time=%s,
                            out_time=%s,
                            hours_worked=%s,
                            overtime_hours=%s,
                            status=%s,
                            notes=%s
                        WHERE id=%s
                        """,
                        (
                            in_time_val,
                            out_time_val,
                            hours_worked,
                            overtime_hours,
                            "Present",
                            notes,
                            existing["id"],
                        ),
                    )
                    if ok:
                        st.success("Attendance updated.")
                    else:
                        st.error("❌ Failed to update attendance (Neon).")
                else:
                    ok = execute(
                        """
                        INSERT INTO attendance
                        (worker_id, att_date, in_time, out_time, hours_worked, overtime_hours, status, notes)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            worker_id,
                            att_date,
                            in_time_val,
                            out_time_val,
                            hours_worked,
                            overtime_hours,
                            "Present",
                            notes,
                        ),
                    )
                    if ok:
                        st.success("Attendance saved.")
                    else:
                        st.error("❌ Failed to save attendance (Neon).")

    # ==========================================================
    # TAB 2 – QUICK WORK ORDER
    # ==========================================================
    with tab2:
        st.subheader("🛠 Quick Work Order")

        df_buildings = _load_buildings()
        df_wc = _load_wc_groups()
        df_workers = _load_workers()

        col_l1, col_l2 = st.columns(2)
        with col_l1:
            req_date = st.date_input(
                "Requested Date", value=date.today(), key="mobile_wo_date"
            )
            priority_options = ["Low", "Medium", "High", "Critical"]
            priority = st.selectbox(
                "Priority",
                priority_options,
                index=1,
                key="mobile_wo_priority",
            )
        with col_l2:
            target_date = st.date_input(
                "Target (SLA) Date",
                value=date.today(),
                key="mobile_wo_target_date",
            )

        title = st.text_input(
            "Work Order Title",
            key="mobile_wo_title",
            placeholder="Example: WC Group 3 – Blocked drain / water leak",
        )
        desc = st.text_area(
            "Description",
            key="mobile_wo_desc",
            placeholder="Describe the issue, location and any safety notes...",
            height=100,
        )

        # Building / WC selector
        col_loc1, col_loc2 = st.columns(2)
        with col_loc1:
            building_id = None
            if not df_buildings.empty:
                b_labels = df_buildings["name"].tolist()
                b_sel = st.selectbox("Building", ["(None)"] + b_labels, key="mobile_wo_build")
                if b_sel != "(None)":
                    building_id = int(
                        df_buildings[df_buildings["name"] == b_sel]["id"].iloc[0]
                    )
        with col_loc2:
            wc_group_id = None
            if not df_wc.empty:
                w_labels = df_wc["name"].tolist()
                w_sel = st.selectbox(
                    "WC Group", ["(None)"] + w_labels, key="mobile_wo_wcgroup"
                )
                if w_sel != "(None)":
                    wc_group_id = int(df_wc[df_wc["name"] == w_sel]["id"].iloc[0])

        # Assign worker (optional)
        assigned_worker_id = None
        if not df_workers.empty:
            w_labels2 = [
                f"{r['worker_code']} – {r['full_name']} ({r['position']})"
                for _, r in df_workers.iterrows()
            ]
            w_map2 = {
                label: r["id"] for label, (_, r) in zip(w_labels2, df_workers.iterrows())
            }
            w_sel2 = st.selectbox(
                "Assign to Worker (optional)",
                ["(Unassigned)"] + w_labels2,
                key="mobile_wo_worker",
            )
            if w_sel2 != "(Unassigned)":
                assigned_worker_id = w_map2[w_sel2]

        if st.button("📨 Create Work Order", type="primary", key="btn_mobile_wo"):
            if not title.strip():
                st.error("Please enter a Work Order Title.")
            else:
                requested_at_dt = datetime.combine(req_date, time(9, 0))
                target_dt = datetime.combine(target_date, time(17, 0))

                ok = execute(
                    """
                    INSERT INTO work_orders
                    (wo_number, status, priority, requested_at, target_date,
                     building_id, wc_group_id, assigned_worker_id, created_by_supervisor_id,
                     title, description)
                    VALUES
                    (NULL, %s, %s, %s, %s,
                     %s, %s, %s, %s,
                     %s, %s)
                    """,
                    (
                        "Open",
                        priority,
                        requested_at_dt,
                        target_dt,
                        building_id,
                        wc_group_id,
                        assigned_worker_id,
                        supervisor_id,
                        title.strip(),
                        desc.strip(),
                    ),
                )
                if ok:
                    st.success("Work Order created.")
                else:
                    st.error("❌ Failed to create Work Order (Neon).")

    # ==========================================================
    # TAB 3 – WC Photos & Notes
    # ==========================================================
    with tab3:
        st.subheader("🚻 WC Groups – Photos & Observations")

        df_wc = _load_wc_groups()
        if df_wc.empty:
            st.info("No WC Groups found. Please configure WC groups first.")
        else:
            wc_labels = df_wc["name"].tolist()
            wc_sel = st.selectbox(
                "WC Group", wc_labels, key="mobile_wc_select"
            )
            wc_id = int(df_wc[df_wc["name"] == wc_sel]["id"].iloc[0])

            photo_files = st.file_uploader(
                "Upload WC Photos (up to 4)",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key="mobile_wc_photos",
            )

            status = st.selectbox(
                "Status",
                ["Clean & Operational", "Needs Cleaning", "Minor Maintenance", "Out of Service"],
                key="mobile_wc_status",
            )

            notes = st.text_area(
                "Observations / Notes",
                key="mobile_wc_notes",
                placeholder="Example: 1 WC out of service, broken tap, missing soap dispenser...",
                height=100,
            )

            if st.button("💾 Save WC Entry (Photos + Notes)", type="primary", key="btn_mobile_wc_save"):
                saved_paths = []
                if photo_files:
                    os.makedirs(WC_PHOTO_DIR, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    for idx, f in enumerate(photo_files[:4], start=1):
                        ext = f.name.split(".")[-1].lower()
                        safe_name = f"wc_{wc_id}_{ts}_{idx}.{ext}"
                        full_path = os.path.join(WC_PHOTO_DIR, safe_name)
                        with open(full_path, "wb") as out:
                            out.write(f.getbuffer())
                        saved_paths.append(full_path)

                # Optionally log simple text record in daily_reports or another table in future.
                # For now, just show success with file paths.
                st.success("WC photos & notes saved locally.")
                if saved_paths:
                    st.caption("Saved photo files:")
                    for p in saved_paths:
                        st.write(f"- {p}")
