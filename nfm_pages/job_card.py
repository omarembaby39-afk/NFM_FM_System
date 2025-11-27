# job_card.py – Job Card / Work Completion Certificate PDF

import os
import streamlit as st

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


def create_job_card_pdf(
    output_path: str,
    job_no: str,
    work_order_no: str,
    client_name: str,
    location: str,
    date_str: str,
    description: str,
    manpower: str,
    materials: str,
    start_time: str,
    end_time: str,
    remarks: str,
    nfm_logo_path: str = "assets/nfm_logo.png",
    client_logo_path: str = "assets/client_logo.png",
):
    if not REPORTLAB_AVAILABLE:
        return False

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

        # Logos row
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
                    ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ]
            )
        )
        elements.append(header_table)
        elements.append(Spacer(1, 10))

        # Title
        elements.append(Paragraph("Job Card / Work Completion Certificate", title_style))
        elements.append(Spacer(1, 12))

        # Header info
        header_info = [
            Paragraph(f"Job No: {job_no}", normal),
            Paragraph(f"Work Order No: {work_order_no}", normal),
            Paragraph(f"Client: {client_name}", normal),
            Paragraph(f"Location: {location}", normal),
            Paragraph(f"Date: {date_str}", normal),
        ]
        for p in header_info:
            elements.append(p)
        elements.append(Spacer(1, 15))

        # Scope / work description
        elements.append(Paragraph("<b>Scope of Work / Description:</b>", bold))
        for line in description.split("\n"):
            elements.append(Paragraph(line, normal))
        elements.append(Spacer(1, 10))

        # Manpower & materials
        elements.append(Paragraph("<b>Manpower Used:</b>", bold))
        elements.append(Paragraph(manpower or "-", normal))
        elements.append(Spacer(1, 5))

        elements.append(Paragraph("<b>Materials / Spare Parts Used:</b>", bold))
        elements.append(Paragraph(materials or "-", normal))
        elements.append(Spacer(1, 10))

        # Time
        elements.append(Paragraph(f"<b>Work Start Time:</b> {start_time}", bold))
        elements.append(Paragraph(f"<b>Work Completion Time:</b> {end_time}", bold))
        elements.append(Spacer(1, 10))

        # Remarks
        elements.append(Paragraph("<b>Remarks / Comments:</b>", bold))
        for line in remarks.split("\n"):
            elements.append(Paragraph(line, normal))
        elements.append(Spacer(1, 30))

        # Signatures
        sig_table = Table(
            [
                [Paragraph("<b>Prepared by (Contractor):</b>", bold),
                 Paragraph("<b>Verified & Accepted by (Client):</b>", bold)],
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
        return True

    except Exception as e:
        print("❌ Job card PDF error:", e)
        return False


def render():
    st.title("Job Card / Work Completion Certificate")

    if not REPORTLAB_AVAILABLE:
        st.error("ReportLab is not installed. PDF export is disabled.")
        return

    col1, col2 = st.columns(2)
    with col1:
        job_no = st.text_input("Job No", "JC-2025-001")
        work_order_no = st.text_input("Work Order No", "WO-2025-001")
        client_name = st.text_input("Client", "WATANIYA COMPANY – Um Qasr Port")
        location = st.text_input("Location", "Um Qasr Port – Cleaning Area")
        date_str = st.text_input("Date", "2025-11-05")

    with col2:
        start_time = st.text_input("Work Start Time", "08:00")
        end_time = st.text_input("Work Completion Time", "16:30")
        nfm_logo_path = st.text_input("NFM Logo path", "assets/nfm_logo.png")
        client_logo_path = st.text_input("Client Logo path", "assets/client_logo.png")

    st.subheader("Scope / Description of Work")
    description = st.text_area("Description", "Corrective cleaning and waste removal in designated area.")

    st.subheader("Manpower Used")
    manpower = st.text_area("Manpower", "2 x Technicians\n1 x Supervisor")

    st.subheader("Materials / Spare Parts Used")
    materials = st.text_area("Materials", "Detergents, tools, PPE")

    st.subheader("Remarks / Comments")
    remarks = st.text_area("Remarks", "Work completed as per client request. No incidents reported.")

    if st.button("Generate Job Card PDF"):
        output_file = "job_card.pdf"
        ok = create_job_card_pdf(
            output_path=output_file,
            job_no=job_no,
            work_order_no=work_order_no,
            client_name=client_name,
            location=location,
            date_str=date_str,
            description=description,
            manpower=manpower,
            materials=materials,
            start_time=start_time,
            end_time=end_time,
            remarks=remarks,
            nfm_logo_path=nfm_logo_path,
            client_logo_path=client_logo_path,
        )

        if ok and os.path.exists(output_file):
            with open(output_file, "rb") as f:
                st.download_button(
                    "Download Job Card / WCC",
                    data=f,
                    file_name=output_file,
                    mime="application/pdf",
                )
        else:
            st.error("Failed to generate job card PDF. Check logs.")
