# maintenance_invoice.py – Out-of-scope / Repair Maintenance Invoice (Pro layout + auto numbering)

import os
import datetime
import streamlit as st

# --- ReportLab imports (safe) ---
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
    )

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# --- Optional DB helpers ---
try:
    from database_pg import get_next_invoice_number, record_invoice
    DB_HELPERS_AVAILABLE = True
except Exception:
    DB_HELPERS_AVAILABLE = False


def auto_invoice_number_mnt() -> str:
    """
    Get next invoice number for maintenance.
    Uses database helper if available, otherwise timestamp-based.
    Pattern with DB: INV-MNT-YYYY-XXX
    Fallback: INV-MNT-YYYYMMDD-HHMM
    """
    if DB_HELPERS_AVAILABLE:
        try:
            return get_next_invoice_number("MNT")
        except Exception:
            pass

    now = datetime.datetime.now()
    return f"INV-MNT-{now.year}{now.month:02d}{now.day:02d}-{now.hour:02d}{now.minute:02d}"


def create_maintenance_invoice_pdf(
    output_path: str,
    invoice_no: str,
    client_name: str,
    contract_ref: str,
    work_order_no: str,
    period: str,
    items: list,
    overhead_percent: float,
    notes: str,
    nfm_logo_path: str = "assets/nfm_logo.png",
    client_logo_path: str = "assets/client_logo.png",
):
    """
    items = list of dicts: {"desc": str, "qty": float, "unit": str, "rate": float}
    Returns:
        grand_total (float) on success, or None on error.
    """

    if not REPORTLAB_AVAILABLE:
        print("❌ ReportLab not available.")
        return None

    try:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=25 * mm,
            rightMargin=25 * mm,
            topMargin=25 * mm,
            bottomMargin=20 * mm,
        )
        width, height = A4

        styles = getSampleStyleSheet()
        normal = styles["Normal"]
        normal.leading = 14
        title_style = styles["Heading1"]
        title_style.fontSize = 18
        title_style.leading = 22
        bold = ParagraphStyle("Bold", parent=normal, fontName="Helvetica-Bold")

        elements = []

        # ---------- logos ----------
        header_row = []

        if os.path.exists(nfm_logo_path):
            nfm_img = Image(nfm_logo_path, width=35 * mm, height=20 * mm)
        else:
            nfm_img = Paragraph("", normal)

        if os.path.exists(client_logo_path):
            client_img = Image(client_logo_path, width=35 * mm, height=20 * mm)
        else:
            client_img = Paragraph("", normal)

        header_row.append(nfm_img)
        header_row.append(Paragraph("", normal))
        header_row.append(client_img)

        header_table = Table(
            [header_row],
            colWidths=[40 * mm, width - (40 * mm) * 2 - 50, 40 * mm],
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, 0), "LEFT"),
                    ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ]
            )
        )
        elements.append(header_table)
        elements.append(Spacer(1, 10))

        # ---------- title ----------
        elements.append(
            Paragraph("Facility Management – Maintenance Invoice (Out of Scope)", title_style)
        )
        elements.append(Spacer(1, 12))

        # ---------- header info ----------
        header_info = [
            Paragraph(f"Invoice No: {invoice_no}", normal),
            Paragraph(f"Client: {client_name}", normal),
            Paragraph(f"Contract Reference: {contract_ref}", normal),
            Paragraph(f"Work Order No: {work_order_no}", normal),
            Paragraph(f"Period / Date: {period}", normal),
        ]
        for p in header_info:
            elements.append(p)
        elements.append(Spacer(1, 15))

        # ---------- items table ----------
        data = [
            [
                Paragraph("<b>Description</b>", bold),
                Paragraph("<b>Qty</b>", bold),
                Paragraph("<b>Unit</b>", bold),
                Paragraph("<b>Rate</b>", bold),
                Paragraph("<b>Amount</b>", bold),
            ]
        ]

        subtotal = 0.0
        for item in items:
            qty = float(item.get("qty") or 0)
            rate = float(item.get("rate") or 0)
            amount = qty * rate
            subtotal += amount
            data.append(
                [
                    item.get("desc", ""),
                    f"{qty:.2f}",
                    item.get("unit", ""),
                    f"{rate:,.3f}",
                    f"{amount:,.3f}",
                ]
            )

        overhead_percent = float(overhead_percent or 0)
        overhead_amount = round(subtotal * overhead_percent / 100.0, 3)
        grand_total = round(subtotal + overhead_amount, 3)

        # subtotal, overhead, total rows
        data.append(
            [
                Paragraph("<b>Subtotal</b>", bold),
                "",
                "",
                "",
                Paragraph(f"<b>{subtotal:,.3f}</b>", bold),
            ]
        )
        data.append(
            [
                Paragraph(f"<b>Overhead ({overhead_percent:.2f}%)</b>", bold),
                "",
                "",
                "",
                Paragraph(f"<b>{overhead_amount:,.3f}</b>", bold),
            ]
        )
        data.append(
            [
                Paragraph("<b>Grand Total</b>", bold),
                "",
                "",
                "",
                Paragraph(f"<b>{grand_total:,.3f}</b>", bold),
            ]
        )

        table = Table(
            data,
            colWidths=[80 * mm, 20 * mm, 20 * mm, 30 * mm, 40 * mm],
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("ALIGN", (3, 1), (4, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BACKGROUND", (0, -3), (-1, -1), colors.whitesmoke),
                    ("FONTNAME", (0, -3), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 15))

        # ---------- notes ----------
        elements.append(Paragraph("<b>Scope / Notes:</b>", bold))
        if notes:
            for line in notes.split("\n"):
                elements.append(
                    Paragraph(line, ParagraphStyle("notes", parent=normal, italic=True))
                )
        elements.append(Spacer(1, 40))

        # ---------- signatures ----------
        sig_table = Table(
            [
                [
                    Paragraph("<b>Prepared by (Contractor):</b>", bold),
                    Paragraph("<b>Verified & Accepted by (Client):</b>", bold),
                ],
                ["", ""],
            ],
            colWidths=[80 * mm, 80 * mm],
        )
        sig_table.setStyle(
            TableStyle(
                [
                    ("LINEABOVE", (0, 1), (0, 1), 0.75, colors.black),
                    ("LINEABOVE", (1, 1), (1, 1), 0.75, colors.black),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(sig_table)

        doc.build(elements)
        print(f"✔ Maintenance invoice PDF generated at: {output_path}")
        return grand_total

    except Exception as e:
        print("❌ Error while generating maintenance invoice:", e)
        return None


def render():
    """Streamlit page for out-of-scope / repair maintenance invoice."""
    st.title("Maintenance Invoice – Out of Scope")

    if not REPORTLAB_AVAILABLE:
        st.error("ReportLab is not installed. PDF export is disabled.")
        return

    st.markdown("Use this invoice for **extra maintenance / repairs** not included in the monthly contract.")

    auto_no = auto_invoice_number_mnt()
    invoice_no = st.text_input("Invoice No", auto_no)

    client_name = st.text_input("Client", "WATANIYA COMPANY – Um Qasr Port")
    contract_ref = st.text_input("Contract Reference", "NFM-UMQASR-FM-001")
    work_order_no = st.text_input("Work Order No", "WO-2025-001")
    period = st.text_input("Date / Period", "2025/11/05")

    st.subheader("Maintenance Items (up to 5 lines)")

    items = []
    for i in range(1, 6):
        with st.expander(f"Item {i}", expanded=(i == 1)):
            desc = st.text_input(f"Description {i}", "", key=f"desc_{i}")
            qty = st.number_input(f"Qty {i}", min_value=0.0, value=0.0, step=1.0, key=f"qty_{i}")
            unit = st.text_input(f"Unit {i}", "Job", key=f"unit_{i}")
            rate = st.number_input(
                f"Rate {i} (IQD)", min_value=0.0, value=0.0, step=1000.0, key=f"rate_{i}"
            )
            if desc and qty > 0 and rate > 0:
                items.append({"desc": desc, "qty": qty, "unit": unit, "rate": rate})

    overhead_percent = st.number_input("Overhead (%)", min_value=0.0, value=0.0, step=0.5)

    st.subheader("Scope / Notes")
    notes = st.text_area("Short description of work / scope", "Corrective maintenance – out of contract scope.")

    st.subheader("Logos (optional)")
    nfm_logo_path = st.text_input("NFM Logo path", "assets/nfm_logo.png")
    client_logo_path = st.text_input("Client Logo path", "assets/client_logo.png")

    if st.button("Generate Maintenance Invoice PDF"):
        output_file = "maintenance_invoice.pdf"
        grand_total = create_maintenance_invoice_pdf(
            output_path=output_file,
            invoice_no=invoice_no,
            client_name=client_name,
            contract_ref=contract_ref,
            work_order_no=work_order_no,
            period=period,
            items=items,
            overhead_percent=overhead_percent,
            notes=notes,
            nfm_logo_path=nfm_logo_path,
            client_logo_path=client_logo_path,
        )

        if grand_total is not None and os.path.exists(output_file):
            if DB_HELPERS_AVAILABLE:
                try:
                    record_invoice(
                        invoice_no=invoice_no,
                        invoice_type="MNT",
                        client_name=client_name,
                        contract_ref=contract_ref,
                        period=period,
                        total_amount=float(grand_total),
                    )
                except Exception:
                    pass

            with open(output_file, "rb") as f:
                st.download_button(
                    "Download Maintenance Invoice PDF",
                    data=f,
                    file_name=output_file,
                    mime="application/pdf",
                )
        else:
            st.error("Failed to generate maintenance invoice PDF. Check input and logs.")
