# invoice_pdf.py – PDF generator for NFM FM System
# Clean, fixed, and Streamlit-Cloud safe version

import streamlit as st

# -------------------------------------------------------
# 1) Safe import for ReportLab (required for PDF output)
# -------------------------------------------------------
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


# -------------------------------------------------------
# 2) Check availability function
# -------------------------------------------------------
def is_pdf_enabled():
    """Return True if ReportLab is installed."""
    return REPORTLAB_AVAILABLE


# -------------------------------------------------------
# 3) Create simple PDF (example function – you can expand)
# -------------------------------------------------------
def create_invoice_pdf(output_path, title="Invoice", lines=None):
    """
    Generate a PDF invoice.
    output_path: full output filename including .pdf
    title: page title
    lines: list of text lines to write in PDF
    """

    if not REPORTLAB_AVAILABLE:
        print("❌ ReportLab is NOT installed – PDF generation disabled.")
        return False

    try:
        c = canvas.Canvas(output_path, pagesize=A4)

        width, height = A4
        y = height - 50

        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, title)
        y -= 40

        # Body lines
        if lines:
            c.setFont("Helvetica", 12)
            for line in lines:
                c.drawString(50, y, str(line))
                y -= 20

        c.showPage()
        c.save()
        print(f"✔ PDF saved: {output_path}")
        return True

    except Exception as e:
        print("❌ PDF generation error:", e)
        return False


# -------------------------------------------------------
# 4) Streamlit UI helper
# -------------------------------------------------------
def generate_pdf_ui():
    """
    Optional: Streamlit UI button to generate a sample PDF.
    This will be called by render().
    """

    st.subheader("Generate Invoice PDF")

    if not REPORTLAB_AVAILABLE:
        st.error("ReportLab is not installed. PDF export is disabled.")
        return

    title = st.text_input("Invoice title", "NFM Invoice Example")

    default_lines = [
        "Line 1: Example service",
        "Line 2: Example amount",
        "Line 3: Thank you for using NPS."
    ]
    lines_text = st.text_area(
        "Invoice lines (one per row)",
        "\n".join(default_lines),
        height=150,
    )
    lines = [l for l in lines_text.split("\n") if l.strip()]

    if st.button("Generate PDF"):
        output_file = "invoice_output.pdf"

        ok = create_invoice_pdf(
            output_file,
            title=title,
            lines=lines,
        )

        if ok:
            with open(output_file, "rb") as f:
                st.download_button(
                    "Download Invoice PDF",
                    data=f,
                    file_name=output_file,
                    mime="application/pdf"
                )


# -------------------------------------------------------
# 5) Standard page entry point for PAGE_MAP
# -------------------------------------------------------
def render():
    """Entry point for the Invoice PDF page (used by PAGE_MAP)."""
    st.title("Invoice PDF Generator")

    if not REPORTLAB_AVAILABLE:
        st.error("ReportLab is not installed. PDF export is disabled.")
        return

    generate_pdf_ui()
