import os
from datetime import date
from calendar import month_name

import pandas as pd
import streamlit as st

from database_pg import fetch_all
from config import LOCAL_DATA_DIR

# Optional: reportlab for PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Folder to store monthly reports
FM_REPORT_DIR = os.path.join(LOCAL_DATA_DIR, "fm_monthly_reports")
os.makedirs(FM_REPORT_DIR, exist_ok=True)


# -------------------------------------------------
# Helpers to load data from Neon
# -------------------------------------------------
def _load_attendance(year: int, month: int) -> pd.DataFrame:
    rows = fetch_all(
        """
        SELECT a.att_date, a.status, w.worker_code, w.full_name, w.position
        FROM attendance a
        LEFT JOIN workers w ON a.worker_id = w.id
        WHERE EXTRACT(YEAR FROM a.att_date) = %s
          AND EXTRACT(MONTH FROM a.att_date) = %s
        ORDER BY a.att_date, w.worker_code
        """,
        (year, month),
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_work_orders(year: int, month: int) -> pd.DataFrame:
    rows = fetch_all(
        """
        SELECT id, wo_number, status, category, assigned_to, opened_at, closed_at, building_id, wc_group_id
        FROM work_orders
        WHERE EXTRACT(YEAR FROM opened_at) = %s
          AND EXTRACT(MONTH FROM opened_at) = %s
        ORDER BY opened_at
        """,
        (year, month),
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_fleet(year: int, month: int) -> pd.DataFrame:
    # Ensure fleet tables exist & load joined view
    rows = fetch_all(
        """
        SELECT
            f.used_date,
            v.name AS vehicle_name,
            f.hours_used,
            f.total_cost
        FROM fleet_timesheet f
        LEFT JOIN fleet_vehicles v ON f.vehicle_id = v.id
        WHERE EXTRACT(YEAR FROM f.used_date) = %s
          AND EXTRACT(MONTH FROM f.used_date) = %s
        ORDER BY f.used_date
        """,
        (year, month),
    )
    df = pd.DataFrame(rows) if rows else pd.DataFrame()

    if df.empty:
        return df

    # Safe numeric conversion
    df["hours_used"] = pd.to_numeric(df.get("hours_used", 0), errors="coerce").fillna(0.0)
    df["total_cost"] = pd.to_numeric(df.get("total_cost", 0), errors="coerce").fillna(0.0)

    # Ensure vehicle_name always string
    if "vehicle_name" not in df.columns:
        df["vehicle_name"] = "N/A"
    else:
        df["vehicle_name"] = df["vehicle_name"].astype(str).fillna("N/A")

    return df


# -------------------------------------------------
# PDF generator
# -------------------------------------------------
def _generate_pdf(year: int, month: int, att_df: pd.DataFrame,
                  wo_df: pd.DataFrame, fl_df: pd.DataFrame) -> str:
    """Generate monthly FM summary PDF and return file path."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab is not installed. Run: pip install reportlab")

    month_label = f"{month_name[month]} {year}"
    filename = f"FM_Monthly_Report_{year}_{month:02d}.pdf"
    pdf_path = os.path.join(FM_REPORT_DIR, filename)

    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    def header():
        c.setFont("Helvetica-Bold", 14)
        c.drawString(20 * mm, height - 20 * mm, "Nile Facility Management – Um Qasr Welcome Yard")
        c.setFont("Helvetica", 11)
        c.drawString(20 * mm, height - 27 * mm, f"Monthly FM Summary – {month_label}")
        c.line(15 * mm, height - 30 * mm, width - 15 * mm, height - 30 * mm)

    def section_title(y, text):
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20 * mm, y, text)
        return y - 6 * mm

    def text_line(y, label, value):
        c.setFont("Helvetica", 10)
        c.drawString(22 * mm, y, f"{label}: {value}")
        return y - 5 * mm

    # ---------- PAGE 1: KPI Summary ----------
    header()
    y = height - 40 * mm

    # Attendance KPI
    total_att = len(att_df)
    total_present = (att_df["status"] == "Present").sum() if not att_df.empty and "status" in att_df.columns else 0
    total_absent = (att_df["status"] == "Absent").sum() if not att_df.empty and "status" in att_df.columns else 0

    y = section_title(y, "1. Attendance Summary")
    y = text_line(y, "Total Attendance Records", total_att)
    y = text_line(y, "Present", total_present)
    y = text_line(y, "Absent", total_absent)

    # Work Orders KPI
    total_wo = len(wo_df)
    closed_wo = (wo_df["status"].isin(["Completed", "Closed"])).sum() if not wo_df.empty and "status" in wo_df.columns else 0
    open_wo = (wo_df["status"].isin(["Open", "In Progress"])).sum() if not wo_df.empty and "status" in wo_df.columns else 0

    y -= 5 * mm
    y = section_title(y, "2. Work Orders Summary")
    y = text_line(y, "Total Work Orders", total_wo)
    y = text_line(y, "Open / In Progress", open_wo)
    y = text_line(y, "Completed / Closed", closed_wo)

    # Fleet KPI
    total_hours = 0.0
    total_cost = 0.0
    if not fl_df.empty:
        total_hours = float(fl_df["hours_used"].sum())
        total_cost = float(fl_df["total_cost"].sum())

    y -= 5 * mm
    y = section_title(y, "3. Fleet Usage Summary")
    y = text_line(y, "Total Hours (all vehicles)", f"{total_hours:.1f}")
    y = text_line(y, "Total Fleet Cost (IQD)", f"{total_cost:,.0f}")

    c.showPage()

    # ---------- PAGE 2: Fleet Breakdown ----------
    header()
    y = height - 40 * mm
    y = section_title(y, "Fleet Usage Breakdown")

    if fl_df.empty:
        c.setFont("Helvetica", 10)
        c.drawString(22 * mm, y, "No fleet records for this month.")
    else:
        # aggregate by vehicle
        grp = (
            fl_df.groupby("vehicle_name", dropna=False)
            .agg(hours=("hours_used", "sum"), cost=("total_cost", "sum"))
            .reset_index()
        )

        c.setFont("Helvetica-Bold", 10)
        c.drawString(22 * mm, y, "Vehicle")
        c.drawString(90 * mm, y, "Hours")
        c.drawString(120 * mm, y, "Cost (IQD)")
        y -= 6 * mm

        c.setFont("Helvetica", 9)
        for _, r in grp.iterrows():
            # SAFELY handle vehicle_name
            veh = r.get("vehicle_name", "N/A")
            if pd.isna(veh):
                veh = "N/A"
            veh = str(veh)[:20]

            hours = float(r.get("hours", 0) or 0)
            cost_val = float(r.get("cost", 0) or 0)

            c.drawString(22 * mm, y, veh)
            c.drawRightString(105 * mm, y, f"{hours:.1f}")
            c.drawRightString(145 * mm, y, f"{cost_val:,.0f}")
            y -= 5 * mm

            if y < 25 * mm:
                c.showPage()
                header()
                y = height - 40 * mm
                c.setFont("Helvetica-Bold", 10)
                c.drawString(22 * mm, y, "Vehicle")
                c.drawString(90 * mm, y, "Hours")
                c.drawString(120 * mm, y, "Cost (IQD)")
                y -= 6 * mm
                c.setFont("Helvetica", 9)

    c.save()
    return pdf_path


# -------------------------------------------------
# Streamlit page render
# -------------------------------------------------
def render():
    st.title("📅 Monthly FM Report – Um Qasr Welcome Yard")
    st.caption("Generate printable monthly summary (Attendance, Work Orders, Fleet).")

    today = date.today()
    col1, col2 = st.columns(2)

    with col1:
        year = st.number_input(
            "Year",
            min_value=2024,
            max_value=2100,
            value=today.year,
            step=1,
        )
    with col2:
        month = st.number_input(
            "Month",
            min_value=1,
            max_value=12,
            value=today.month,
            step=1,
        )

    if st.button("📄 Generate Monthly PDF", type="primary"):
        att_df = _load_attendance(int(year), int(month))
        wo_df = _load_work_orders(int(year), int(month))
        fl_df = _load_fleet(int(year), int(month))

        if not REPORTLAB_AVAILABLE:
            st.error("ReportLab not installed. Run in venv: pip install reportlab")
            return

        try:
            pdf_path = _generate_pdf(int(year), int(month), att_df, wo_df, fl_df)
        except Exception as e:
            st.error(f"Failed to generate PDF: {e}")
            return

        st.success("Monthly report generated successfully.")
        st.write("Saved to:", pdf_path)

        # If you want, also provide a download button:
        try:
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="⬇ Download PDF",
                    data=f.read(),
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf",
                )
        except FileNotFoundError:
            st.warning("PDF file not found on disk after generation.")
