import os
import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

from database_pg import fetch_all
from config import LOCAL_DATA_DIR


def render():
    st.title("💰 Payroll – NFM Workers")

    st.caption(
        "Monthly payroll estimation based on Attendance (hours & overtime) and Worker salaries "
        "for Nile Facility Management – Um Qasr Welcome Yard."
    )

    # -------------------------------
    # Period selection
    # -------------------------------
    today = date.today()
    col1, col2, col3 = st.columns(3)
    with col1:
        year = st.number_input("Year", min_value=2020, max_value=2100, value=today.year, step=1)
    with col2:
        month = st.number_input("Month", min_value=1, max_value=12, value=today.month, step=1)
    with col3:
        only_active = st.checkbox("Only Active workers", value=True, key="payroll_only_active")

    month_start = date(int(year), int(month), 1)
    month_end = month_start + relativedelta(months=1) - relativedelta(days=1)

    st.markdown(f"**Payroll period:** {month_start} → {month_end}")

    # -------------------------------
    # Fetch aggregated data from Neon
    # -------------------------------
    filter_status = ""
    if only_active:
        filter_status = "AND w.status='Active'"

    rows = fetch_all(
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
        (month_start, month_end),
    )

    if not rows:
        st.info("No attendance / payroll data for this month.")
        return

    df = pd.DataFrame(rows)

    # -------------------------------
    # Compute payroll from hours
    # -------------------------------

    def compute_pay(row):
        """
        Simple rule:
        - Assume 26 working days per month, 8 hours per day.
        - Hourly rate = salary / (26 * 8).
        - Basic pay = hourly_rate * total_hours.
        - OT pay   = hourly_rate * total_ot (x1).
        """
        salary = float(row.get("salary") or 0)
        if salary <= 0:
            return 0.0, 0.0, 0.0
        hourly_rate = salary / (26 * 8)
        basic_hours = float(row.get("total_hours") or 0)
        ot_hours = float(row.get("total_ot") or 0)
        basic_pay = hourly_rate * basic_hours
        ot_pay = hourly_rate * ot_hours
        total_pay = basic_pay + ot_pay
        return basic_pay, ot_pay, total_pay

    basic_pay_list = []
    ot_pay_list = []
    total_pay_list = []

    for _, r in df.iterrows():
        b, o, t = compute_pay(r)
        basic_pay_list.append(round(b, 0))
        ot_pay_list.append(round(o, 0))
        total_pay_list.append(round(t, 0))

    df["Basic_Pay_Est"] = basic_pay_list
    df["OT_Pay_Est"] = ot_pay_list
    df["Total_Pay_Est"] = total_pay_list

    # -------------------------------
    # Totals & KPIs
    # -------------------------------
    total_workers = len(df)
    sum_basic = df["Basic_Pay_Est"].sum()
    sum_ot = df["OT_Pay_Est"].sum()
    sum_total = df["Total_Pay_Est"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Workers in payroll", f"{total_workers}")
    c2.metric("Total Basic Pay (IQD)", f"{sum_basic:,.0f}")
    c3.metric("Total OT Pay (IQD)", f"{sum_ot:,.0f}")
    c4.metric("Grand Total (IQD)", f"{sum_total:,.0f}")

    st.markdown("---")

    # -------------------------------
    # Show payroll table
    # -------------------------------
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
    show_cols = [c for c in show_cols if c in df.columns]

    st.subheader("Payroll Detail")
    st.dataframe(df[show_cols], use_container_width=True)

    # -------------------------------
    # Export to OneDrive & download
    # -------------------------------
    file_name = f"payroll_{year}_{month:02d}.csv"

    saved_msg = ""
    try:
        os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
        local_path = os.path.join(LOCAL_DATA_DIR, file_name)
        df[show_cols].to_csv(local_path, index=False, encoding="utf-8")
        saved_msg = f"Saved a copy to OneDrive folder: {local_path}"
    except Exception as e:
        saved_msg = f"⚠️ Could not save to LOCAL_DATA_DIR ({LOCAL_DATA_DIR}): {e}"

    csv_data = df[show_cols].to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇️ Download Payroll CSV",
        data=csv_data,
        file_name=file_name,
        mime="text/csv",
        key="btn_export_payroll",
    )

    st.caption(saved_msg)
