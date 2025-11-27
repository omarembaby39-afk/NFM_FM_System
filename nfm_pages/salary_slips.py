import os
from datetime import date, datetime

import pandas as pd
import streamlit as st
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors

from database_pg import fetch_all
from config import LOCAL_DATA_DIR, WORKER_PHOTO_DIR, NFM_LOGO, APP_TITLE


SLIP_DIR = os.path.join(LOCAL_DATA_DIR, "salary_slips")
os.makedirs(SLIP_DIR, exist_ok=True)


def _load_workers():
    rows = fetch_all(
        """
        SELECT id, worker_code, full_name, position, nationality, salary
        FROM workers
        WHERE status = 'Active'
        ORDER BY worker_code
        """
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_attendance(worker_id: int, year: int, month: int):
    rows = fetch_all(
        """
        SELECT att_date, status, hours_worked, overtime_hours
        FROM attendance
        WHERE worker_id = %s
          AND EXTRACT(YEAR FROM att_date) = %s
          AND EXTRACT(MONTH FROM att_date) = %s
        """,
        (worker_id, year, month),
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _find_photo(worker_code: str):
    for ext in ("jpg", "jpeg", "png"):
        path = os.path.join(WORKER_PHOTO_DIR, f"{worker_code}.{ext}")
        if os.path.exists(path):
            return path
    return None


def _generate_slip(worker, df_att, year: int, month: int):
    filename = f"Salary_Slip_{worker['worker_code']}_{year}_{month:02d}.pdf"
    full_path = os.path.join(SLIP_DIR, filename)

    c = canvas.Canvas(full_path, pagesize=A4)
    width, height = A4

    # Header
    try:
        c.drawImage(NFM_LOGO, 15 * mm, height - 35 * mm, width=30 * mm, preserveAspectRatio=True)
    except Exception:
        pass

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50 * mm, height - 25 * mm, APP_TITLE)

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50 * mm, height - 35 * mm, "Salary Slip")

    c.setFont("Helvetica", 11)
    c.drawString(50 * mm, height - 43 * mm, f"Period: {year}-{month:02d}")
    c.drawString(50 * mm, height - 51 * mm, f"Generated: {datetime.now().strftime('%Y-%m-%d')}")

    # Worker photo (if exists)
    photo_path = _find_photo(worker["worker_code"])
    if photo_path:
        try:
            c.drawImage(photo_path, width - 45 * mm, height - 50 * mm, width=25 * mm, height=30 * mm, preserveAspectRatio=True)
        except Exception:
            pass

    # Worker Info
    y = height - 70 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, y, "Worker Information")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Code: {worker['worker_code']}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Name: {worker['full_name']}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Position: {worker['position']}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Nationality: {worker['nationality']}")
    y -= 10 * mm

    # Attendance Summary
    days_present = (df_att["status"] == "Present").sum() if not df_att.empty else 0
    days_absent = (df_att["status"] == "Absent").sum() if not df_att.empty else 0
    days_leave = (df_att["status"] == "Leave").sum() if not df_att.empty else 0
    total_hours = float(df_att["hours_worked"].fillna(0).sum()) if not df_att.empty else 0.0
    total_ot = float(df_att["overtime_hours"].fillna(0).sum()) if not df_att.empty else 0.0

    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, y, "Attendance Summary")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Days Present: {days_present}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Days Absent: {days_absent}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Days Leave: {days_leave}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Total Hours: {total_hours:.1f}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Overtime Hours: {total_ot:.1f}")
    y -= 10 * mm

    # Salary Calculation
    basic = float(worker["salary"] or 0.0)
    # very simple OT rate assumption
    # daily = salary / 26 days, hourly = daily / 8 hours
    if basic > 0:
        ot_rate = basic / 26.0 / 8.0
    else:
        ot_rate = 0.0
    ot_amount = total_ot * ot_rate
    gross = basic + ot_amount

    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, y, "Salary Summary (IQD)")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Basic Salary: {basic:,.0f}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"OT Hours: {total_ot:.1f} @ {ot_rate:,.0f} / hr")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"OT Amount: {ot_amount:,.0f}")
    y -= 5 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, f"Gross Pay: {gross:,.0f}")
    y -= 15 * mm

    # Footer
    c.setFont("Helvetica", 9)
    c.drawString(15 * mm, 30 * mm, "Prepared by: Nile Facility Management – HR & Payroll")
    c.drawString(15 * mm, 23 * mm, "This slip is system-generated based on attendance and basic salary.")

    c.showPage()
    c.save()

    return full_path


def render():
    st.title("💰 Salary Slip with Photo")

    df_workers = _load_workers()
    if df_workers.empty:
        st.info("No workers found. Please configure workers first.")
        return

    labels = [
        f"{r['worker_code']} – {r['full_name']} ({r['position']})"
        for _, r in df_workers.iterrows()
    ]
    id_map = {lbl: r["id"] for lbl, (_, r) in zip(labels, df_workers.iterrows())}

    sel_label = st.selectbox("Select Worker", labels, key="slip_worker_sel")
    worker_id = id_map[sel_label]
    worker = df_workers[df_workers["id"] == worker_id].iloc[0]

    today = date.today()
    col1, col2 = st.columns(2)
    with col1:
        year = st.number_input("Year", min_value=2024, max_value=2100, value=today.year, key="slip_year")
    with col2:
        month = st.number_input("Month", min_value=1, max_value=12, value=today.month, key="slip_month")

    if st.button("Generate Salary Slip PDF", type="primary", key="slip_generate_btn"):
        df_att = _load_attendance(worker_id, int(year), int(month))
        slip_path = _generate_slip(worker, df_att, int(year), int(month))

        st.success(f"Salary slip generated: {slip_path}")
        with open(slip_path, "rb") as f:
            st.download_button(
                "⬇ Download Salary Slip",
                f,
                file_name=os.path.basename(slip_path),
                mime="application/pdf",
            )
