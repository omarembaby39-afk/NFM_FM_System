# app.py – NFM Facility Management System

import warnings
import streamlit as st
from config import APP_TITLE

warnings.filterwarnings("ignore")

# -------------------------------------------------
# Import all page modules
# -------------------------------------------------
from nfm_pages import (
    dashboard,
    wc_groups,
    buildings,
    building_inspections,
    fleet,
    work_orders,
    daily_reports,
    workers,
    attendance,
    payroll,
    invoices,
    kpi,
    sla,
    supervisor_mobile,
    settings_page,
    monthly_report,
    salary_slips,
)

import nfm_pages.invoice_pdf as invoice_pdf
import nfm_pages.maintenance_invoice as maintenance_invoice
import nfm_pages.job_card as job_card
import nfm_pages.vehicle_timesheets as vehicle_timesheets

# -------------------------------------------------
# Streamlit page config (must be before any UI)
# -------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------
# Patch deprecated use_container_width
# -------------------------------------------------
_original_plotly_chart = st.plotly_chart


def _patched_plotly_chart(*args, **kwargs):
    # Replace deprecated use_container_width with width="stretch"
    if "use_container_width" in kwargs:
        val = kwargs.pop("use_container_width")
        kwargs["width"] = "stretch" if val else "content"
    return _original_plotly_chart(*args, **kwargs)


st.plotly_chart = _patched_plotly_chart

_original_data_frame = st.dataframe


def _patched_data_frame(*args, **kwargs):
    # Replace deprecated use_container_width with width="stretch"
    if "use_container_width" in kwargs:
        val = kwargs.pop("use_container_width")
        kwargs["width"] = "stretch" if val else "content"
    return _original_data_frame(*args, **kwargs)


st.dataframe = _patched_data_frame

# -------------------------------------------------
# Page registry (name → module with render())
# -------------------------------------------------
PAGE_MAP = {
    # Overview
    "Dashboard": dashboard,
    "FM Monthly Report": monthly_report,
    "Worker KPIs": kpi,
    "SLA Dashboard": sla,

    # Operations
    "WC Groups": wc_groups,
    "Buildings": buildings,
    "Building Inspections": building_inspections,
    "Fleet & Equipment": fleet,
    "Work Orders": work_orders,
    "Daily Reports": daily_reports,
    "Vehicle Time Sheets": vehicle_timesheets,
    "Job Card / Work Completion Certificate": job_card,

    # HR & Attendance
    "Workers & Attendance": workers,
    "Attendance": attendance,
    "Payroll": payroll,
    "Salary Slips": salary_slips,
    "Supervisor Mobile": supervisor_mobile,

    # Billing & Invoices
    "Invoices": invoices,
    "Invoice PDF": invoice_pdf,
    "Maintenance Invoice (Out of Scope)": maintenance_invoice,

    # Settings
    "Settings & Help": settings_page,
}

# -------------------------------------------------
# Sidebar sections (grouped navigation)
# -------------------------------------------------
SECTIONS = {
    "📊 Overview": [
        "Dashboard",
        "FM Monthly Report",
        "Worker KPIs",
        "SLA Dashboard",
    ],
    "🏗️ Operations": [
        "WC Groups",
        "Buildings",
        "Building Inspections",
        "Fleet & Equipment",
        "Work Orders",
        "Daily Reports",
        "Vehicle Time Sheets",
        "Job Card / Work Completion Certificate",
    ],
    "👥 HR & Attendance": [
        "Workers & Attendance",
        "Attendance",
        "Payroll",
        "Salary Slips",
        "Supervisor Mobile",
    ],
    "💰 Billing & Invoices": [
        "Invoices",
        "Invoice PDF",
        "Maintenance Invoice (Out of Scope)",
    ],
    "⚙️ Settings": [
        "Settings & Help",
    ],
}

# -------------------------------------------------
# Main app
# -------------------------------------------------
def main():
    # Sidebar header
    st.sidebar.markdown("### 🧭 NFM FM System")
    st.sidebar.caption("Nile Projects Service – Um Qasr Yard")

    # Choose module / section
    section_names = list(SECTIONS.keys())
    section = st.sidebar.selectbox("Module", section_names, index=0)

    # Pages inside chosen section
    pages_in_section = [name for name in SECTIONS[section] if name in PAGE_MAP]

    # Choose page within module
    page_name = st.sidebar.radio(
        "Page",
        pages_in_section,
        index=0,
        key=f"page_radio_{section}",
    )

    # Main title + context
    st.title(APP_TITLE)
    st.markdown(f"**Module:** {section}  \n**Page:** {page_name}")

    # Render selected page
    PAGE_MAP[page_name].render()


# -------------------------------------------------
# Entry point
# -------------------------------------------------
if __name__ == "__main__":
    main()
