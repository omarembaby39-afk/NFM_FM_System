import os
import streamlit as st
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

from config import (
    LOCAL_DATA_DIR,
    ASSETS_DIR,
    NFM_LOGO,
    CLIENT_LOGO,
)

from database_pg import fetch_all


def generate_pdf(invoice):
    """Generate invoice PDF and save to OneDrive folder."""

    file_path = os.path.join(
        LOCAL_DATA_DIR,
        f"Invoice_{invoice['invoice_no']}.pdf"
    )

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    # -------------------------------------------------
    # Logos
    # -------------------------------------------------
    try:
        c.drawImage(NFM_LOGO, 20*mm, height - 40*mm, width=40*mm, preserveAspectRatio=True)
    except:
        pass

    try:
        c.drawImage(CLIENT_LOGO, width - 60*mm, height - 40*mm, width=40*mm, preserveAspectRatio=True)
    except:
        pass

    # -------------------------------------------------
    # Header
    # -------------------------------------------------
    c.setFont("Helvetica-Bold", 18)
    c.drawString(20*mm, height - 50*mm, "Facility Management – Monthly Invoice")

    c.setFont("Helvetica", 12)
    c.drawString(20*mm, height - 60*mm, f"Invoice No: {invoice['invoice_no']}")
    c.drawString(20*mm, height - 68*mm, f"Client: {invoice['client_name']}")
    c.drawString(20*mm, height - 76*mm, f"Contract Reference: {invoice['contract_ref']}")
    c.drawString(20*mm, height - 84*mm, f"Period: {invoice['year']}/{invoice['month']:02d}")

    # -------------------------------------------------
    # Summary Table
    # -------------------------------------------------
    data = [
        ["Description", "IQD"],
        ["Labour Total", f"{invoice['labour_total']:,.0f}"],
        ["Fleet Total", f"{invoice['fleet_total']:,.0f}"],
        ["Other Charges", f"{invoice['other_total']:,.0f}"],
        [f"Overhead ({invoice['overhead_pct']}%)", f"{invoice['overhead_amount']:,.0f}"],
        ["Grand Total", f"{invoice['grand_total']:,.0f}"],
    ]

    table = Table(data, colWidths=[100*mm, 70*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))

    table.wrapOn(c, 20*mm, height - 150*mm)
    table.drawOn(c, 20*mm, height - 150*mm)

    # -------------------------------------------------
    # Notes
    # -------------------------------------------------
    c.setFont("Helvetica", 11)
    c.drawString(20*mm, height - 165*mm, "Notes:")
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(20*mm, height - 175*mm, invoice["notes"][:120])

    # -------------------------------------------------
    # Signature block
    # -------------------------------------------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20*mm, 40*mm, "Prepared by:")
    c.drawString(100*mm, 40*mm, "Approved by:")

    c.line(20*mm, 35*mm, 80*mm, 35*mm)
    c.line(100*mm, 35*mm, 160*mm, 35*mm)

    # -------------------------------------------------
    # Finish
    # -------------------------------------------------
    c.showPage()
    c.save()

    return file_path


# ---------------------------------------------------------
# Streamlit Page
# ---------------------------------------------------------
def render():
    st.title("📄 Generate PDF Invoice")

    rows = fetch_all("SELECT * FROM invoices ORDER BY year DESC, month DESC, id DESC LIMIT 20")

    if not rows:
        st.warning("No invoices found. Please create an invoice first.")
        return

    df = {r["invoice_no"]: r for r in rows}

    selected = st.selectbox("Select Invoice", list(df.keys()))

    invoice = df[selected]

    if st.button("Generate PDF Invoice", type="primary"):
        file_path = generate_pdf(invoice)
        st.success(f"PDF saved: {file_path}")

        with open(file_path, "rb") as f:
            st.download_button(
                "⬇ Download PDF",
                f,
                file_name=os.path.basename(file_path),
                mime="application/pdf"
            )
