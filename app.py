import streamlit as st
from config import APP_TITLE
from nfm_pages import invoice_pdf
import warnings
warnings.filterwarnings("ignore")
import nfm_pages.maintenance_invoice as maintenance_invoice
import nfm_pages.job_card as job_card
import nfm_pages.vehicle_timesheets as vehicle_timesheets
from nfm_pages import (
    dashboard,
    wc_groups,
    buildings,
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
    building_inspections, 
    maintenance_invoice,
     job_card,
      vehicle_timesheets,
    )
# -----------------------------------------------
# Patch: Replace deprecated use_container_width
# -----------------------------------------------
import streamlit as st

# Monkey-patch deprecated parameter to silence warnings
_original_plotly_chart = st.plotly_chart
def _patched_plotly_chart(*args, **kwargs):
    if "use_container_width" in kwargs:
        val = kwargs.pop("use_container_width")
        kwargs["width"] = "stretch" if val else "content"
    return _original_plotly_chart(*args, **kwargs)

st.plotly_chart = _patched_plotly_chart

_original_data_frame = st.dataframe
def _patched_data_frame(*args, **kwargs):
    if "use_container_width" in kwargs:
        val = kwargs.pop("use_container_width")
        kwargs["width"] = "stretch" if val else "content"
    return _original_data_frame(*args, **kwargs)

st.dataframe = _patched_data_frame

# Streamlit page config MUST be at top
st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGE_MAP = {
    "Dashboard": dashboard,
    "WC Groups": wc_groups,
    "Buildings": buildings,
    "Building Inspections": building_inspections,
    "Fleet & Equipment": fleet,
    "Work Orders": work_orders,
    "Daily Reports": daily_reports,
    "Workers & Attendance": workers,
    "Attendance": attendance,
    "Payroll": payroll,
    "Invoices": invoices,
    "Invoice PDF": invoice_pdf,
    "FM Monthly Report": monthly_report,
    "Salary Slips": salary_slips,
    "Worker KPIs": kpi,
    "SLA Dashboard": sla,
    "Supervisor Mobile": supervisor_mobile,
    "Settings & Help": settings_page,
    "Maintenance Invoice (Out of Scope)": maintenance_invoice,
    "Job Card / Work Completion Certificate": job_card,
    "Vehicle Time Sheets": vehicle_timesheets,
}


def main():
    st.sidebar.title("Nile Facility Management")
    page_name = st.sidebar.radio(
        "Navigation",
        list(PAGE_MAP.keys()),
        index=0,
    )

    # Call the selected page's render() function
    PAGE_MAP[page_name].render()


if __name__ == "__main__":
    main()
