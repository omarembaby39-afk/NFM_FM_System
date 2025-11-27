# invoice_pdf.py – Facility Management Monthly Invoice (Pro layout + auto numbering)

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

# --- Optional DB helpers (Neon) ---
try:
    from database_pg import get_next_invoice_number, record_invoice
    DB_HELPERS_AVAILABLE = True
except Exception:
    DB_HELPERS_AVAILABLE = False


# --------------------------
# Helper: auto invoice no
# --------------------------
def auto_invoice_number_fm() -> str:
    """
    Get next invoice number for monthly FM.
    Uses database helper if available, otherwise timestamp-based.
    Pattern with DB: INV-FM-YYYY-XXX
    Fallback: INV-FM-YYYYMMDD-HHMM
    """
    if DB_HELPERS_AVAILABLE:
        try:
            return get_next_invoice_number("FM")
        except Exception:
            pass

    now = datetime.datetime.now()
    return f"INV-FM-{now.year}{now.month:02d}{now.day:02d}-{now.hour:02d}{now.minute:02d}"


# --------------------------
# Core PDF generator
# --------------------------
def create_invoice_pdf(
    output_path: str,
    invoice_no: str,
    client_name: str,
    contract_ref: str,
    period: str,
    labour_total: float,
    fleet_total: float,
    other_charges: float,
    overhead_percent: float,
    notes: str,
    nfm_logo_path: str = "assets/nfm_logo.png",
    client_logo_path: str = "assets/client_logo.png",
):
    """
    Generate a Facility Management – Monthly Invoice PDF using professional layout.

    Returns:
        grand_total (float) on success, or None on error.
    """

    if not REPORTLAB_AVAILABLE:
        print("❌ ReportLab not available, cannot generate PDF.")
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

        # ---------- Header with logos ----------
        header_row = []

        # NFM logo (left)
        if os.path.exists(nfm_logo_path):
            nfm_img = Image(nfm_logo_path, width=35 * mm, height=20 * mm)
        else:
            nfm_img = Paragraph("", normal)

        # Client logo (right)
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

        # ---------- Title ----------
        elements.append(Paragraph("Facility Management – Monthly Invoice", title_style))
        elements.append(Spacer(1, 12))

        # ---------- Header info ----------
        header_info = [
            Paragraph(f"Invoice No: {invoice_no}", normal),
            Paragraph(f"Client: {client_name}", normal),
            Paragraph(f"Contract Reference: {contract_ref}", normal),
            Paragraph(f"Period: {period}", normal),
        ]

        for p in header_info:
            elements.append(p)
        elements.append(Spacer(1, 15))

        # ---------- Financial table ----------
        labour_total = float(labour_total or 0)
        fleet_total = float(fleet_total or 0)
        other_charges = float(other_charges or 0)
        overhead_percent = float(overhead_percent or 0)

        subtotal = labour_total + fleet_total + other_charges
        overhead_amount = round(subtotal * overhead_percent / 100.0, 3)
        grand_total = round(subtotal + overhead_amount, 3)

        data = [
            [Paragraph("<b>Description</b>", bold), Paragraph("<b>IQD</b>", bold)],
            ["Labour Total", f"{labour_total:,.3f}"],
            ["Fleet Total", f"{fleet_total:,.3f}"],
            ["Other Charges", f"{other_charges:,.3f}"],
            [f"Overhead ({overhead_percent:.2f}%)", f"{overhead_amount:,.3f}"],
            [Paragraph("<b>Grand Total</b>", bold), Paragraph(f"<b>{grand_total:,.3f}</b>", bold)],
        ]

        table = Table(
            data,
            colWidths=[100 * mm, 50 * mm],
            hAlign="LEFT",
        )

        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 15))

        # ---------- Notes ----------
        elements.append(Paragraph("<b>Notes:</b>", bold))
        if notes:
            for line in notes.split("\n"):
                elements.append(Paragraph(line, ParagraphStyle("notes", parent=normal, italic=True)))
        elements.append(Spacer(1, 40))

        # ---------- Signatures ----------
        sig_table = Table(
            [
                [
                    Paragraph("<b>Prepared by:</b>", bold),
                    Paragraph("<b>Approved by:</b>", bold),
                ],
                ["", ""],
            ],
            colWidths=[70 * mm, 70 * mm],
        )
        sig_table.setStyle(
            TableStyle(
                [
                    ("LINEABOVE", (0, 1), (0, 1), 0.75, colors.black),
                    ("LINEABOVE", (1, 1), (1, 1), 0.75, colors.black),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            )
        )

        elements.append(sig_table)

        # ---------- Build PDF ----------
        doc.build(elements)
        print(f"✔ Invoice PDF generated at: {output_path}")
        return grand_total

    except Exception as e:
        print("❌ Error while generating invoice PDF:", e)
        return None


# --------------------------
# Streamlit page
# --------------------------
def render():
    """Streamlit page for generating monthly FM invoice PDFs."""
    st.title("Facility Management – Monthly Invoice")

    if not REPORTLAB_AVAILABLE:
        st.error("ReportLab is not installed. PDF export is disabled.")
        return

    with st.form("invoice_form"):
        st.subheader("Invoice Header")

        auto_no = auto_invoice_number_fm()
        invoice_no = st.text_input("Invoice No", auto_no)
        client_name = st.text_input("Client", "WATANIYA COMPANY – Um Qasr Port")
        contract_ref = st.text_input("Contract Reference", "NFM-UMQASR-FM-001")
        period = st.text_input("Period (YYYY/MM)", "2025/11")

        st.subheader("Financials (IQD)")
        labour_total = st.number_input("Labour Total", min_value=0.0, value=48.0, step=1.0)
        fleet_total = st.number_input("Fleet Total", min_value=0.0, value=750000.0, step=1000.0)
        other_charges = st.number_input("Other Charges", min_value=0.0, value=0.0, step=1000.0)
        overhead_percent = st.number_input("Overhead (%)", min_value=0.0, value=15.0, step=0.5)

        st.subheader("Notes")
        notes = st.text_area("Notes", "CLEANING AREA")

        st.subheader("Logos (optional)")
        nfm_logo_path = st.text_input("NFM Logo path", "assets/nfm_logo.png")
        client_logo_path = st.text_input("Client Logo path", "assets/client_logo.png")

        submitted = st.form_submit_button("Generate Monthly Invoice PDF")

    if submitted:
        output_file = "facility_invoice.pdf"
        grand_total = create_invoice_pdf(
            output_path=output_file,
            invoice_no=invoice_no,
            client_name=client_name,
            contract_ref=contract_ref,
            period=period,
            labour_total=labour_total,
            fleet_total=fleet_total,
            other_charges=other_charges,
            overhead_percent=overhead_percent,
            notes=notes,
            nfm_logo_path=nfm_logo_path,
            client_logo_path=client_logo_path,
        )

        if grand_total is not None and os.path.exists(output_file):
            # Optional: record in DB
            if DB_HELPERS_AVAILABLE:
                try:
                    record_invoice(
                        invoice_no=invoice_no,
                        invoice_type="FM",
                        client_name=client_name,
                        contract_ref=contract_ref,
                        period=period,
                        total_amount=float(grand_total),
                    )
                except Exception:
                    pass

            with open(output_file, "rb") as f:
                st.download_button(
                    "Download Monthly Invoice PDF",
                    data=f,
                    file_name=output_file,
                    mime="application/pdf",
                )
        else:
            st.error("Failed to generate invoice PDF. Check logs for details.")
