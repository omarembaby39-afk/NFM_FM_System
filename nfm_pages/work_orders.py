import os
from datetime import date

import pandas as pd
import streamlit as st

from database_pg import fetch_all, execute
from config import LOCAL_DATA_DIR

# Optional PDF support
try:
    from reportlab.lib.pagesizes import A5, B5
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

WO_EXPORT_DIR = os.path.join(LOCAL_DATA_DIR, "work_orders")
os.makedirs(WO_EXPORT_DIR, exist_ok=True)


# -------------------------------------------------
# DB helpers
# -------------------------------------------------
def ensure_tables():
    """Create / migrate work_orders table."""
    execute(
        """
        CREATE TABLE IF NOT EXISTS work_orders (
            id SERIAL PRIMARY KEY,
            wo_number TEXT UNIQUE,
            title TEXT NOT NULL,
            description TEXT,
            requested_by TEXT,
            priority TEXT,
            location_type TEXT,            -- WC / Building / Yard
            building_id INTEGER,
            wc_group_id INTEGER,
            sla_hours INTEGER,
            target_date DATE,
            assigned_to TEXT,
            status TEXT DEFAULT 'Open',
            opened_at TIMESTAMP DEFAULT NOW(),
            closed_at TIMESTAMP,
            internal_notes TEXT
        );
        """,
        (),
    )

    # migrations for older schema
    execute(
        "ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS location_type TEXT",
        (),
    )


def generate_next_wo_number() -> str:
    """
    Generate next WO number in format: NPS-WO-XXX
    Examples: NPS-WO-001, NPS-WO-002, ...
    """
    rows = fetch_all(
        """
        SELECT wo_number
        FROM work_orders
        WHERE wo_number IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
        """
    )
    if not rows:
        return "NPS-WO-001"

    last = rows[0].get("wo_number") or "NPS-WO-000"
    try:
        parts = last.split("-")
        num_part = parts[-1]
        prefix = "-".join(parts[:-1]) or "NPS-WO"
        new_num = int(num_part) + 1
        return f"{prefix}-{new_num:03d}"
    except Exception:
        # Fallback if old format is weird
        return "NPS-WO-001"


def load_buildings():
    rows = fetch_all(
        "SELECT id, building_name FROM buildings ORDER BY building_name"
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def load_wc_groups():
    rows = fetch_all(
        "SELECT id, group_name FROM wc_groups ORDER BY group_name"
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def load_technicians():
    rows = fetch_all(
        """
        SELECT id, worker_code, full_name, position
        FROM workers
        WHERE status = 'Active'
        ORDER BY worker_code
        """
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def load_wo_list():
    rows = fetch_all(
        """
        SELECT id, wo_number, title, status, priority, location_type,
               target_date, assigned_to, opened_at
        FROM work_orders
        ORDER BY opened_at DESC
        LIMIT 200
        """
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def load_wo_by_id(wo_id: int):
    rows = fetch_all(
        "SELECT * FROM work_orders WHERE id = %s",
        (wo_id,),
    )
    return rows[0] if rows else None


# -------------------------------------------------
# PDF / Excel export
# -------------------------------------------------
def export_wo_to_pdf(wo: dict, page_size_label: str) -> str:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab not installed. Run: pip install reportlab")

    if page_size_label == "B5":
        pagesize = B5
    else:
        pagesize = A5

    filename = f"{wo.get('wo_number','NPS-WO')}.pdf"
    pdf_path = os.path.join(WO_EXPORT_DIR, filename)

    c = canvas.Canvas(pdf_path, pagesize=pagesize)
    width, height = pagesize

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(15 * mm, height - 20 * mm, "Nile Facility Management")
    c.setFont("Helvetica", 11)
    c.drawString(15 * mm, height - 27 * mm, "Um Qasr Welcome Yard – Work Order")
    c.line(10 * mm, height - 30 * mm, width - 10 * mm, height - 30 * mm)

    y = height - 40 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, y, f"WO No.: {wo.get('wo_number','')}")
    opened_at = str(wo.get("opened_at", "") or "")
    c.drawRightString(width - 15 * mm, y, f"Date: {opened_at[:10]}")
    y -= 8 * mm

    # Basic info
    def line(label, value):
        nonlocal y
        c.setFont("Helvetica-Bold", 9)
        c.drawString(15 * mm, y, f"{label}:")
        c.setFont("Helvetica", 9)
        c.drawString(40 * mm, y, str(value)[:60])
        y -= 5 * mm

    line("Title", wo.get("title", ""))
    line("Requested By", wo.get("requested_by", ""))
    line("Priority", wo.get("priority", ""))
    line("Assigned To", wo.get("assigned_to", ""))
    line("Location Type", wo.get("location_type", ""))
    line("Target Date", str(wo.get("target_date", "") or ""))

    # Description
    y -= 5 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(15 * mm, y, "Description:")
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    desc = str(wo.get("description", "") or "")
    for line_text in split_text(desc, 80):
        c.drawString(17 * mm, y, line_text)
        y -= 4 * mm
        if y < 20 * mm:
            c.showPage()
            y = height - 20 * mm

    # Internal notes
    y -= 5 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(15 * mm, y, "Internal Notes / Technician Feedback:")
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    notes = str(wo.get("internal_notes", "") or "")
    if not notes.strip():
        notes = "_______________________________"
    for line_text in split_text(notes, 80):
        c.drawString(17 * mm, y, line_text)
        y -= 4 * mm
        if y < 20 * mm:
            c.showPage()
            y = height - 20 * mm

    # Footer for signatures
    y -= 10 * mm
    c.setFont("Helvetica", 9)
    c.drawString(15 * mm, y, "Requester Signature: ______________________")
    c.drawRightString(width - 15 * mm, y, "Technician Signature: ______________________")

    c.save()
    return pdf_path


def split_text(text: str, width: int):
    """Simple word-wrap helper for PDF."""
    words = text.split()
    line = []
    for w in words:
        line.append(w)
        if len(" ".join(line)) > width:
            yield " ".join(line)
            line = []
    if line:
        yield " ".join(line)


def export_wo_to_excel(wo: dict) -> str:
    filename = f"{wo.get('wo_number','NPS-WO')}.xlsx"
    xlsx_path = os.path.join(WO_EXPORT_DIR, filename)

    df = pd.DataFrame([wo])
    try:
        df.to_excel(xlsx_path, index=False)
    except Exception as e:
        raise RuntimeError(
            f"Excel export failed ({e}). You may need: pip install openpyxl"
        )
    return xlsx_path


# -------------------------------------------------
# Streamlit page
# -------------------------------------------------
def render():
    st.title("🛠 Work Orders")

    ensure_tables()

    buildings_df = load_buildings()
    wc_df = load_wc_groups()
    tech_df = load_technicians()

    st.markdown("### ➕ Create New Work Order")

    col_main, col_side = st.columns([2, 1])

    with col_main:
        title = st.text_input("Title", key="wo_title")
        description = st.text_area("Description", key="wo_desc", height=100)
        requested_by = st.text_input("Requested By", key="wo_req_by")
        priority = st.selectbox(
            "Priority",
            ["Low", "Medium", "High", "Urgent"],
            index=1,
            key="wo_priority",
        )

        internal_notes = st.text_area(
            "Internal Notes",
            key="wo_notes",
            height=60,
        )

    with col_side:
        # Location type: WC / Building / Yard & Public
        location_type = st.selectbox(
            "Location Type",
            ["WC", "Building", "Yard & Public"],
            key="wo_location_type",
        )

        # Related building
        building_id = None
        if location_type == "Building" and not buildings_df.empty:
            b_labels = ["(None)"] + list(buildings_df["building_name"])
            sel_b = st.selectbox(
                "Related Building",
                b_labels,
                key="wo_building",
            )
            if sel_b != "(None)":
                row_b = buildings_df[buildings_df["building_name"] == sel_b].iloc[0]
                building_id = int(row_b["id"])

        # Related WC group
        wc_group_id = None
        if location_type == "WC" and not wc_df.empty:
            w_labels = ["(None)"] + list(wc_df["group_name"])
            sel_w = st.selectbox(
                "Related WC Group",
                w_labels,
                key="wo_wc_group",
            )
            if sel_w != "(None)":
                row_w = wc_df[wc_df["group_name"] == sel_w].iloc[0]
                wc_group_id = int(row_w["id"])

        sla_hours = st.number_input(
            "SLA (hours)",
            min_value=1,
            max_value=240,
            value=24,
            step=1,
            key="wo_sla",
        )

        target_date = st.date_input(
            "Target Date",
            value=date.today(),
            key="wo_target_date",
        )

        # Assigned to
        assigned_to = ""
        if not tech_df.empty:
            t_labels = ["(None)"] + [
                f"{r['worker_code']} – {r['full_name']}"
                for _, r in tech_df.iterrows()
            ]
            sel_t = st.selectbox(
                "Assigned To (Technician/Team)",
                t_labels,
                key="wo_assigned_to",
            )
            if sel_t != "(None)":
                assigned_to = sel_t

    if st.button("Save Work Order", type="primary", key="btn_save_wo"):
        if not title.strip():
            st.error("Title is required.")
        else:
            wo_number = generate_next_wo_number()
            ok = execute(
                """
                INSERT INTO work_orders
                (wo_number, title, description, requested_by, priority,
                 location_type, building_id, wc_group_id, sla_hours,
                 target_date, assigned_to, status, internal_notes)
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    wo_number,
                    title.strip(),
                    description.strip(),
                    requested_by.strip(),
                    priority,
                    location_type,
                    building_id,
                    wc_group_id,
                    sla_hours,
                    target_date,
                    assigned_to,
                    "Open",
                    internal_notes.strip(),
                ),
            )
            if ok:
                st.success(f"Work Order {wo_number} created successfully.")
                st.rerun()
            else:
                st.error("❌ Failed to save Work Order.")

    st.markdown("---")
    st.markdown("### 📋 Existing Work Orders")

    df_wo = load_wo_list()
    if df_wo.empty:
        st.info("No work orders yet.")
        return

    st.dataframe(df_wo, width="stretch")

    st.markdown("### 📤 Export Work Order to PDF / Excel")

    # Select WO to export
    df_wo = df_wo.sort_values("opened_at", ascending=False)
    labels = [
        f"{r['wo_number']} – {r['title'][:40]}"
        for _, r in df_wo.iterrows()
    ]
    id_map = {label: int(r["id"]) for label, (_, r) in zip(labels, df_wo.iterrows())}

    sel_label = st.selectbox(
        "Select Work Order",
        labels,
        key="wo_export_sel",
    )
    sel_id = id_map[sel_label]

    col_exp1, col_exp2, col_exp3 = st.columns([1, 1, 2])

    with col_exp1:
        pdf_size = st.selectbox(
            "PDF Size",
            ["A5", "B5"],
            key="wo_pdf_size",
        )

    with col_exp2:
        do_pdf = st.button("⬇ Export to PDF", key="wo_export_pdf")
    with col_exp3:
        do_xlsx = st.button("⬇ Export to Excel", key="wo_export_xlsx")

    wo_row = load_wo_by_id(sel_id)
    if wo_row is None:
        st.warning("Selected Work Order not found in database.")
        return

    if do_pdf:
        try:
            pdf_path = export_wo_to_pdf(wo_row, pdf_size)
            st.success(f"PDF generated: {pdf_path}")
            try:
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "Download PDF",
                        data=f.read(),
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf",
                        key="wo_pdf_dl",
                    )
            except FileNotFoundError:
                st.warning("PDF file not found on disk.")
        except Exception as e:
            st.error(f"PDF export failed: {e}")

    if do_xlsx:
        try:
            xlsx_path = export_wo_to_excel(wo_row)
            st.success(f"Excel file generated: {xlsx_path}")
            try:
                with open(xlsx_path, "rb") as f:
                    st.download_button(
                        "Download Excel",
                        data=f.read(),
                        file_name=os.path.basename(xlsx_path),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="wo_xlsx_dl",
                    )
            except FileNotFoundError:
                st.warning("Excel file not found on disk.")
        except Exception as e:
            st.error(f"Excel export failed: {e}")
