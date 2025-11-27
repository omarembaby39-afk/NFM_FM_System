# vehicle_timesheets.py – Monthly time sheet + monthly slip for vehicles/equipment

import os
from datetime import date

import pandas as pd
import streamlit as st

from database_pg import fetch_all, execute
from config import LOCAL_DATA_DIR

# Optional PDF support
try:
    from reportlab.lib.pagesizes import A4, A5
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

TS_EXPORT_DIR = os.path.join(LOCAL_DATA_DIR, "vehicle_timesheets")
os.makedirs(TS_EXPORT_DIR, exist_ok=True)


# -------------------------------------------------
# DB helpers
# -------------------------------------------------
def ensure_tables():
    """Create / migrate vehicle timesheet tables."""
    execute(
        """
        CREATE TABLE IF NOT EXISTS vehicle_timesheets (
            id              SERIAL PRIMARY KEY,
            equipment_code  TEXT,
            equipment_name  TEXT,
            month           INTEGER,
            year            INTEGER,
            project_name    TEXT,
            operator_name   TEXT,
            UNIQUE (equipment_code, month, year)
        );
        """,
        (),
    )

    execute(
        """
        CREATE TABLE IF NOT EXISTS vehicle_timesheet_entries (
            id              SERIAL PRIMARY KEY,
            timesheet_id    INTEGER REFERENCES vehicle_timesheets(id) ON DELETE CASCADE,
            work_date       DATE,
            shift_name      TEXT,
            hours_worked    NUMERIC,
            km_start        NUMERIC,
            km_end          NUMERIC,
            fuel_liters     NUMERIC,
            job_description TEXT,
            remarks         TEXT
        );
        """,
        (),
    )


def get_or_create_timesheet(equipment_code, equipment_name, month, year, project, operator):
    """Return timesheet row (dict). Create if not exists."""
    rows = fetch_all(
        """
        SELECT *
        FROM vehicle_timesheets
        WHERE equipment_code = %s AND month = %s AND year = %s
        """,
        (equipment_code, month, year),
    )
    if rows:
        return rows[0]

    ok = execute(
        """
        INSERT INTO vehicle_timesheets
            (equipment_code, equipment_name, month, year, project_name, operator_name)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (equipment_code, equipment_name, month, year, project, operator),
    )
    if not ok:
        return None

    rows = fetch_all(
        """
        SELECT *
        FROM vehicle_timesheets
        WHERE equipment_code = %s AND month = %s AND year = %s
        """,
        (equipment_code, month, year),
    )
    return rows[0] if rows else None


def load_timesheet_entries(ts_id: int):
    rows = fetch_all(
        """
        SELECT *
        FROM vehicle_timesheet_entries
        WHERE timesheet_id = %s
        ORDER BY work_date, id
        """,
        (ts_id,),
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def add_timesheet_entry(
    ts_id: int,
    work_date: date,
    shift_name: str,
    hours_worked: float,
    km_start: float,
    km_end: float,
    fuel_liters: float,
    job_description: str,
    remarks: str,
):
    return execute(
        """
        INSERT INTO vehicle_timesheet_entries
        (timesheet_id, work_date, shift_name, hours_worked, km_start, km_end,
         fuel_liters, job_description, remarks)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            ts_id,
            work_date,
            shift_name,
            hours_worked,
            km_start,
            km_end,
            fuel_liters,
            job_description,
            remarks,
        ),
    )


# -------------------------------------------------
# Export helpers
# -------------------------------------------------
def export_timesheet_to_excel(header: dict, df: pd.DataFrame) -> str:
    filename = f"{header['equipment_code']}_{header['year']}-{header['month']:02d}.xlsx"
    path = os.path.join(TS_EXPORT_DIR, filename)

    df_export = df.copy()
    if not df_export.empty:
        df_export["km_diff"] = df_export["km_end"].fillna(0) - df_export["km_start"].fillna(0)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        hdr_df = pd.DataFrame(
            [
                {
                    "Equipment Code": header["equipment_code"],
                    "Equipment Name": header["equipment_name"],
                    "Month": header["month"],
                    "Year": header["year"],
                    "Project": header["project_name"],
                    "Operator": header["operator_name"],
                }
            ]
        )
        hdr_df.to_excel(writer, sheet_name="Header", index=False)
        df_export.to_excel(writer, sheet_name="Entries", index=False)

    return path


def export_timesheet_to_pdf(header: dict, df: pd.DataFrame) -> str:
    """Detailed monthly timesheet – A4 with all daily rows."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab not installed. Run: pip install reportlab")

    filename = f"{header['equipment_code']}_{header['year']}-{header['month']:02d}_timesheet.pdf"
    path = os.path.join(TS_EXPORT_DIR, filename)

    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    # Header block
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, height - 20 * mm, "Nile Projects Service – Fleet Time Sheet")
    c.setFont("Helvetica", 11)
    c.drawString(
        20 * mm,
        height - 26 * mm,
        f"Equipment: {header['equipment_code']} – {header['equipment_name']}",
    )
    c.drawString(
        20 * mm,
        height - 32 * mm,
        f"Month / Year: {header['month']:02d}/{header['year']}   Project: {header['project_name'] or ''}",
    )
    c.drawString(
        20 * mm,
        height - 38 * mm,
        f"Operator: {header['operator_name'] or ''}",
    )
    c.line(15 * mm, height - 42 * mm, width - 15 * mm, height - 42 * mm)

    y = height - 50 * mm

    # Table header
    c.setFont("Helvetica-Bold", 9)
    headers = [
        "Date",
        "Shift",
        "Hours",
        "Km Start",
        "Km End",
        "Fuel (L)",
        "Job Description",
    ]
    col_x = [18, 34, 46, 60, 74, 90, 110]  # in mm

    for x_mm, text in zip(col_x, headers):
        c.drawString(x_mm * mm, y, text)
    y -= 5 * mm
    c.line(15 * mm, y, width - 15 * mm, y)
    y -= 3 * mm

    c.setFont("Helvetica", 8)

    total_hours = 0.0
    total_fuel = 0.0

    if not df.empty:
        df = df.sort_values("work_date")
        for _, row in df.iterrows():
            if y < 20 * mm:
                c.showPage()
                y = height - 20 * mm
                c.setFont("Helvetica", 8)

            work_date = row.get("work_date")
            shift = row.get("shift_name") or ""
            hours = float(row.get("hours_worked") or 0)
            km_start = row.get("km_start") or 0
            km_end = row.get("km_end") or 0
            fuel = float(row.get("fuel_liters") or 0)
            job_desc = (row.get("job_description") or "")[:60]

            total_hours += hours
            total_fuel += fuel

            c.drawString(col_x[0] * mm, y, str(work_date))
            c.drawString(col_x[1] * mm, y, shift)
            c.drawRightString(col_x[2] * mm + 10 * mm, y, f"{hours:.2f}")
            c.drawRightString(col_x[3] * mm + 12 * mm, y, f"{km_start:.0f}")
            c.drawRightString(col_x[4] * mm + 12 * mm, y, f"{km_end:.0f}")
            c.drawRightString(col_x[5] * mm + 12 * mm, y, f"{fuel:.1f}")
            c.drawString(col_x[6] * mm, y, job_desc)

            y -= 4 * mm

    # Totals row
    y -= 4 * mm
    c.line(15 * mm, y, width - 15 * mm, y)
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(18 * mm, y, "TOTAL:")
    c.drawRightString(col_x[2] * mm + 10 * mm, y, f"{total_hours:.2f} h")
    c.drawRightString(col_x[5] * mm + 12 * mm, y, f"{total_fuel:.1f} L")

    # Signatures
    y -= 20 * mm
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, "Prepared by: ______________________")
    c.drawString(90 * mm, y, "Approved by: ______________________")

    c.save()
    return path


def export_monthly_slip_to_pdf(header: dict, df: pd.DataFrame) -> str:
    """
    Compact monthly slip – A5, summary only (for each equipment).
    Shows totals and key info, like a 'vehicle payslip'.
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab not installed. Run: pip install reportlab")

    filename = f"{header['equipment_code']}_{header['year']}-{header['month']:02d}_slip.pdf"
    path = os.path.join(TS_EXPORT_DIR, filename)

    c = canvas.Canvas(path, pagesize=A5)
    width, height = A5

    total_hours = float(df["hours_worked"].fillna(0).sum()) if not df.empty else 0.0
    total_fuel = float(df["fuel_liters"].fillna(0).sum()) if not df.empty else 0.0
    total_days = df["work_date"].nunique() if not df.empty else 0

    # Header
    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, height - 18 * mm, "Nile Projects Service – Vehicle Monthly Slip")

    c.setFont("Helvetica", 9)
    c.drawString(
        15 * mm,
        height - 25 * mm,
        f"Equipment: {header['equipment_code']} – {header['equipment_name']}",
    )
    c.drawString(
        15 * mm,
        height - 31 * mm,
        f"Month / Year: {header['month']:02d}/{header['year']}",
    )
    c.drawString(
        15 * mm,
        height - 37 * mm,
        f"Project: {header['project_name'] or ''}",
    )
    c.drawString(
        15 * mm,
        height - 43 * mm,
        f"Operator / Driver: {header['operator_name'] or ''}",
    )

    c.line(10 * mm, height - 47 * mm, width - 10 * mm, height - 47 * mm)

    y = height - 55 * mm

    # Summary block
    c.setFont("Helvetica-Bold", 10)
    c.drawString(15 * mm, y, "Summary")
    y -= 7 * mm

    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, f"Total Working Days: {total_days}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Total Operating Hours: {total_hours:.1f} h")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Total Fuel Consumption: {total_fuel:.1f} L")
    y -= 5 * mm

    # simple min/max km if available
    if not df.empty:
        km_start_min = df["km_start"].dropna().min() if "km_start" in df.columns else None
        km_end_max = df["km_end"].dropna().max() if "km_end" in df.columns else None
    else:
        km_start_min = None
        km_end_max = None

    if km_start_min is not None and km_end_max is not None:
        y -= 2 * mm
        c.drawString(
            20 * mm,
            y,
            f"Odometer Range: {km_start_min:.0f} km  →  {km_end_max:.0f} km  "
            f"(Diff: {km_end_max - km_start_min:.0f} km)",
        )
        y -= 6 * mm
    else:
        y -= 4 * mm

    # Optional last jobs list (3 most recent)
    if not df.empty:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(15 * mm, y, "Last Jobs:")
        y -= 6 * mm
        c.setFont("Helvetica", 8)

        df_sorted = df.sort_values("work_date", ascending=False).head(3)
        for _, row in df_sorted.iterrows():
            job = (row.get("job_description") or "")[:60]
            wdate = row.get("work_date")
            c.drawString(20 * mm, y, f"{wdate}: {job}")
            y -= 4 * mm

    # Signatures at bottom
    y -= 10 * mm
    c.setFont("Helvetica", 9)
    c.drawString(15 * mm, y, "Fleet Supervisor: ______________________")
    y -= 9 * mm
    c.drawString(15 * mm, y, "Project Manager: _______________________")

    c.save()
    return path


# -------------------------------------------------
# Streamlit page
# -------------------------------------------------
def render():
    st.title("🚚 Vehicle / Equipment Monthly Time Sheet & Slip")

    ensure_tables()

    st.markdown("Use this page to record **daily slips** and export:")
    st.markdown("- Detailed **monthly timesheet (A4)**")
    st.markdown("- Compact **monthly slip (A5)** per equipment")

    # --- Timesheet header section ---
    with st.form("ts_header"):
        col1, col2, col3 = st.columns(3)

        with col1:
            equipment_code = st.text_input("Equipment Code", "EQ-TRK-001")
            equipment_name = st.text_input("Equipment Name", "Water Tanker 10,000 L")

        with col2:
            year = st.number_input(
                "Year", min_value=2020, max_value=2100, value=date.today().year, step=1
            )
            month = st.number_input(
                "Month", min_value=1, max_value=12, value=date.today().month, step=1
            )

        with col3:
            project_name = st.text_input("Project / Site", "Um Qasr Yard")
            operator_name = st.text_input("Operator / Driver", "")

        submitted_header = st.form_submit_button("Load / Create Timesheet")

    if not submitted_header:
        st.info("Select equipment and month, then click **Load / Create Timesheet**.")
        return

    header = get_or_create_timesheet(
        equipment_code.strip(),
        equipment_name.strip(),
        int(month),
        int(year),
        project_name.strip(),
        operator_name.strip(),
    )

    if header is None:
        st.error("Failed to create or load timesheet. Check database connection.")
        return

    st.success(
        f"Timesheet loaded for {header['equipment_code']} – {header['equipment_name']} "
        f"({header['month']:02d}/{header['year']})"
    )

    ts_id = header["id"]

    # --- Add slip / daily entry ---
    st.markdown("### ➕ Add Daily Slip")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        work_date = st.date_input("Work Date", value=date.today(), key="ts_work_date")
        shift_name = st.selectbox("Shift", ["Day", "Night", "Other"], index=0, key="ts_shift")
    with col_b:
        hours_worked = st.number_input(
            "Hours Worked", min_value=0.0, max_value=24.0, value=8.0, step=0.5, key="ts_hours"
        )
        km_start = st.number_input("Km Start", min_value=0.0, value=0.0, step=1.0, key="ts_km_start")
    with col_c:
        km_end = st.number_input("Km End", min_value=0.0, value=0.0, step=1.0, key="ts_km_end")
        fuel_liters = st.number_input("Fuel (L)", min_value=0.0, value=0.0, step=1.0, key="ts_fuel")

    job_description = st.text_area(
        "Job Description", "Road washing / yard cleaning", key="ts_job_desc", height=70
    )
    remarks = st.text_area("Remarks", "", key="ts_remarks", height=50)

    if st.button("Add Slip", type="primary", key="btn_add_slip"):
        ok = add_timesheet_entry(
            ts_id=ts_id,
            work_date=work_date,
            shift_name=shift_name,
            hours_worked=hours_worked,
            km_start=km_start,
            km_end=km_end,
            fuel_liters=fuel_liters,
            job_description=job_description.strip(),
            remarks=remarks.strip(),
        )
        if ok:
            st.success("Slip added to timesheet.")
            st.rerun()
        else:
            st.error("❌ Failed to add slip. Check database and logs.")

    st.markdown("---")
    st.markdown("### 📋 Timesheet Entries")

    df_entries = load_timesheet_entries(ts_id)
    if df_entries.empty:
        st.info("No slips recorded yet for this timesheet.")
        return

    total_hours = float(df_entries["hours_worked"].fillna(0).sum())
    total_fuel = float(df_entries["fuel_liters"].fillna(0).sum())

    col_t1, col_t2 = st.columns(2)
    col_t1.metric("Total Hours", f"{total_hours:.1f} h")
    col_t2.metric("Total Fuel", f"{total_fuel:.1f} L")

    st.dataframe(
        df_entries[
            ["work_date", "shift_name", "hours_worked", "km_start", "km_end", "fuel_liters", "job_description"]
        ],
        use_container_width=True,
    )

    st.markdown("### 📤 Export for This Month / Equipment")

    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        do_pdf_detail = st.button("A4 Timesheet PDF", key="btn_ts_pdf")
    with col_e2:
        do_pdf_slip = st.button("A5 Monthly Slip PDF", key="btn_ts_slip")
    with col_e3:
        do_xlsx = st.button("Excel", key="btn_ts_xlsx")

    if do_pdf_detail:
        try:
            pdf_path = export_timesheet_to_pdf(header, df_entries)
            st.success(f"Detailed PDF generated: {pdf_path}")
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "Download A4 Timesheet PDF",
                    data=f.read(),
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf",
                    key="dl_ts_pdf",
                )
        except Exception as e:
            st.error(f"PDF export failed: {e}")

    if do_pdf_slip:
        try:
            pdf_path = export_monthly_slip_to_pdf(header, df_entries)
            st.success(f"Monthly slip PDF generated: {pdf_path}")
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "Download A5 Monthly Slip PDF",
                    data=f.read(),
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf",
                    key="dl_ts_slip",
                )
        except Exception as e:
            st.error(f"Monthly slip export failed: {e}")

    if do_xlsx:
        try:
            xlsx_path = export_timesheet_to_excel(header, df_entries)
            st.success(f"Excel generated: {xlsx_path}")
            with open(xlsx_path, "rb") as f:
                st.download_button(
                    "Download Excel",
                    data=f.read(),
                    file_name=os.path.basename(xlsx_path),
                    mime=(
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    ),
                    key="dl_ts_xlsx",
                )
        except Exception as e:
            st.error(f"Excel export failed: {e}")
