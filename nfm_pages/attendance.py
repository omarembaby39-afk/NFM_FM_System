import os
import streamlit as st
import pandas as pd
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta

from database_pg import fetch_all, execute
from config import LOCAL_DATA_DIR  # must be defined in config.py


def render():
    st.title("🕒 Attendance & Overtime – NFM Workers")

    st.caption(
        "Daily attendance, in/out time, overtime (x1) and monthly summary for NFM workers "
        "at Um Qasr Welcome Yard. Data is stored in Neon; monthly reports also saved to OneDrive."
    )

    # --------------------------------------------------
    # Load active workers
    # --------------------------------------------------
    workers = fetch_all(
        """
        SELECT id, worker_code, full_name, position, salary, status
        FROM workers
        WHERE status = 'Active'
        ORDER BY worker_code ASC
        """
    )
    df_workers = pd.DataFrame(workers)

    if df_workers.empty:
        st.warning("No active workers found. Please add workers first in the Workers page.")
        return

    tab_daily, tab_month = st.tabs(["📅 Daily Entry", "📆 Monthly Summary"])

    # ======================================================
    # TAB 1 – DAILY ENTRY
    # ======================================================
    with tab_daily:
        st.subheader("Daily Attendance Entry")

        col_top1, col_top2 = st.columns(2)
        with col_top1:
            att_date = st.date_input("Attendance Date", value=date.today(), key="att_date_daily")

        with col_top2:
            worker_labels = [
                f"{r['worker_code']} – {r['full_name']} ({r['position']})"
                for _, r in df_workers.iterrows()
            ]
            worker_id_map = {
                label: r["id"] for label, (_, r) in zip(worker_labels, df_workers.iterrows())
            }
            sel_worker_label = st.selectbox(
                "Worker", worker_labels, key="att_worker_select"
            )

        worker_id = worker_id_map[sel_worker_label]
        worker_row = df_workers[df_workers["id"] == worker_id].iloc[0]

        st.markdown(
            f"**Worker:** {worker_row['worker_code']} – {worker_row['full_name']} "
            f"({worker_row['position']})"
        )

        # Check if attendance already exists for this worker/date
        existing_rows = fetch_all(
            "SELECT * FROM attendance WHERE worker_id=%s AND att_date=%s",
            (worker_id, att_date),
        )
        existing = existing_rows[0] if existing_rows else None

        st.markdown("---")

        col1, col2 = st.columns(2)

        # ---------- LEFT: Status + time ----------
        with col1:
            status_options = ["Present", "Absent", "Leave", "Off"]
            default_status = "Present"
            if existing and existing.get("status") in status_options:
                default_status = existing["status"]

            status = st.selectbox(
                "Attendance Status",
                status_options,
                index=status_options.index(default_status),
                key="att_status",
            )

            # Defaults for in/out
            default_in = time(8, 0)
            default_out = time(17, 0)

            if existing and existing.get("in_time"):
                try:
                    default_in = existing["in_time"]
                except Exception:
                    pass

            if existing and existing.get("out_time"):
                try:
                    default_out = existing["out_time"]
                except Exception:
                    pass

            in_time_val = st.time_input(
                "In Time", value=default_in, key="att_in_time"
            )
            out_time_val = st.time_input(
                "Out Time", value=default_out, key="att_out_time"
            )

        # ---------- RIGHT: Notes + computed hours ----------
        with col2:
            default_notes = existing["notes"] if existing and existing.get("notes") else ""
            notes = st.text_area(
                "Notes",
                value=default_notes,
                height=80,
                key="att_notes",
            )

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

            st.write(f"**Hours Worked:** {hours_worked:.2f} h")
            st.write(f"**Overtime (x1):** {overtime_hours:.2f} h")

        # ---------- Save button ----------
        if st.button("💾 Save Attendance", type="primary", key="btn_save_att"):
            if status != "Present":
                hours_to_save = 0.0
                ot_to_save = 0.0
            else:
                hours_to_save = hours_worked
                ot_to_save = overtime_hours

            if existing:
                # UPDATE existing row
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
                        hours_to_save,
                        ot_to_save,
                        status,
                        notes.strip(),
                        existing["id"],
                    ),
                )
                if ok:
                    st.success("Attendance updated successfully.")
                else:
                    st.error(
                        "❌ Failed to update attendance. "
                        "Make sure Neon DB is reachable and the 'attendance' table exists."
                    )
            else:
                # INSERT new row
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
                        hours_to_save,
                        ot_to_save,
                        status,
                        notes.strip(),
                    ),
                )
                if ok:
                    st.success("Attendance saved successfully.")
                else:
                    st.error(
                        "❌ Failed to save attendance. "
                        "Check Neon connection and confirm 'attendance' table is created."
                    )

        st.markdown("---")

        # ---------- Recent records ----------
        st.subheader("Recent Attendance for Selected Worker")

        rows_recent = fetch_all(
            """
            SELECT att_date, status, in_time, out_time, hours_worked, overtime_hours, notes
            FROM attendance
            WHERE worker_id=%s
            ORDER BY att_date DESC
            LIMIT 30
            """,
            (worker_id,),
        )

        if rows_recent:
            df_recent = pd.DataFrame(rows_recent)
            st.dataframe(df_recent, use_container_width=True)
        else:
            st.info("No recent attendance records for this worker.")

    # ======================================================
    # TAB 2 – MONTHLY SUMMARY
    # ======================================================
    with tab_month:
        st.subheader("Monthly Attendance & Payroll Summary")

        today = date.today()
        default_year = today.year
        default_month = today.month

        colm1, colm2, colm3 = st.columns(3)
        with colm1:
            year = st.number_input("Year", min_value=2020, max_value=2100, value=default_year, step=1)
        with colm2:
            month = st.number_input("Month", min_value=1, max_value=12, value=default_month, step=1)
        with colm3:
            show_only_active = st.checkbox("Only Active workers", value=True, key="att_only_active")

        month_start = date(int(year), int(month), 1)
        month_end = month_start + relativedelta(months=1) - relativedelta(days=1)

        params = [month_start, month_end]
        filter_status = ""
        if show_only_active:
            filter_status = "AND w.status='Active'"

        rows_sum = fetch_all(
            f"""
            SELECT
                w.worker_code,
                w.full_name,
                w.position,
                w.salary,
                COUNT(CASE WHEN a.status='Present' THEN 1 END) AS days_present,
                COUNT(CASE WHEN a.status='Absent' THEN 1 END) AS days_absent,
                COUNT(CASE WHEN a.status='Leave' THEN 1 END) AS days_leave,
                COALESCE(SUM(a.hours_worked), 0) AS total_hours,
                COALESCE(SUM(a.overtime_hours), 0) AS total_ot
            FROM workers w
            LEFT JOIN attendance a
                ON w.id = a.worker_id
               AND a.att_date BETWEEN %s AND %s
            WHERE 1=1
            {filter_status}
            GROUP BY w.worker_code, w.full_name, w.position, w.salary
            ORDER BY w.worker_code
            """,
            tuple(params),
        )

        if not rows_sum:
            st.info("No attendance data for this month.")
            return

        df_sum = pd.DataFrame(rows_sum)

        # ---------- Compute simple payroll from hours ----------
        def compute_pay(row):
            salary = float(row.get("salary") or 0)
            if salary <= 0:
                return 0.0, 0.0, 0.0
            # Assume 26 working days, 8 hours per day
            hourly_rate = salary / (26 * 8)
            basic_hours = float(row["total_hours"])
            ot_hours = float(row["total_ot"])
            basic_pay = hourly_rate * basic_hours
            ot_pay = hourly_rate * ot_hours  # x1
            total_pay = basic_pay + ot_pay
            return basic_pay, ot_pay, total_pay

        basic_pay_list = []
        ot_pay_list = []
        total_pay_list = []

        for _, r in df_sum.iterrows():
            b, o, t = compute_pay(r)
            basic_pay_list.append(round(b, 0))
            ot_pay_list.append(round(o, 0))
            total_pay_list.append(round(t, 0))

        df_sum["Basic_Pay_Est"] = basic_pay_list
        df_sum["OT_Pay_Est"] = ot_pay_list
        df_sum["Total_Pay_Est"] = total_pay_list

        st.markdown(f"**Summary for {year}-{month:02d}**  ({month_start} → {month_end})")

        show_cols = [
            "worker_code",
            "full_name",
            "position",
            "salary",
            "days_present",
            "days_absent",
            "days_leave",
            "total_hours",
            "total_ot",
            "Basic_Pay_Est",
            "OT_Pay_Est",
            "Total_Pay_Est",
        ]
        show_cols = [c for c in show_cols if c in df_sum.columns]

        st.dataframe(df_sum[show_cols], use_container_width=True)

        # ---------- Export to OneDrive + download ----------
        file_name = f"attendance_summary_{year}_{month:02d}.csv"
        saved_msg = ""

        try:
            os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
            local_path = os.path.join(LOCAL_DATA_DIR, file_name)
            df_sum[show_cols].to_csv(local_path, index=False, encoding="utf-8")
            saved_msg = f"Saved a copy to OneDrive folder: {local_path}"
        except Exception as e:
            saved_msg = f"⚠️ Could not save to LOCAL_DATA_DIR ({LOCAL_DATA_DIR}): {e}"

        csv_data = df_sum[show_cols].to_csv(index=False).encode("utf-8")

        st.download_button(
            "⬇️ Download Monthly Attendance Summary (CSV)",
            data=csv_data,
            file_name=file_name,
            mime="text/csv",
            key="btn_export_att_sum",
        )

        st.caption(saved_msg)
