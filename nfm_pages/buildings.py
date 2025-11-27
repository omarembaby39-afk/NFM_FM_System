import streamlit as st
import pandas as pd
from database_pg import fetch_all, execute


def render():
    st.title("🏢 Buildings – Master Data")

    st.caption(
        "This page manages all buildings in Um Qasr Welcome Yard. "
        "Data is stored in Neon PostgreSQL."
    )

    st.markdown("---")

    # 1) LOAD BUILDINGS
    rows = fetch_all("SELECT * FROM buildings ORDER BY id ASC")
    df = pd.DataFrame(rows)

    if df.empty:
        st.info("No buildings found yet. Use the form below to add the first building.")
    else:
        st.subheader("Existing Buildings")
        show_df = df[["id", "code", "name", "location", "type", "status", "notes"]]
        st.dataframe(show_df, use_container_width=True)

    st.markdown("---")

    # 2) ADD NEW BUILDING
    st.subheader("Add New Building")

    col1, col2 = st.columns(2)
    with col1:
        code = st.text_input("Building Code", placeholder="e.g. B01")
        name = st.text_input("Building Name", placeholder="e.g. Admin Office")
        location = st.text_input("Location", placeholder="e.g. Main Yard")
    with col2:
        btype = st.selectbox("Building Type", [
            "Office", "Control Room", "Store", "Workshop",
            "Gate Cabin", "Container", "Other"
        ])
        status = st.selectbox("Status", ["Clean", "Needs Maintenance", "Out of Service"], index=0)

    notes = st.text_area("Notes", placeholder="Any comments about this building", height=70)

    if st.button("Save Building", type="primary"):
        if not code or not name:
            st.error("Building Code and Name are required.")
        else:
            ok = execute(
                """
                INSERT INTO buildings (code, name, location, type, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (code.strip(), name.strip(), location.strip(), btype, status, notes.strip()),
            )
            if ok:
                st.success("Building saved successfully. Please rerun the app to see it in the table.")
            else:
                st.error("Failed to save building. Check Neon connection or if code is duplicated.")

    # 3) DELETE BUILDING
    st.markdown("---")
    st.subheader("Delete Building (by ID)")

    delete_id = st.number_input("Building ID to delete", min_value=0, value=0, step=1)

    if st.button("Delete Building"):
        if delete_id <= 0:
            st.error("Enter a valid ID.")
        else:
            ok = execute("DELETE FROM buildings WHERE id = %s", (int(delete_id),))
            if ok:
                st.success(f"Building with ID {delete_id} deleted (if it existed).")
            else:
                st.error("Delete failed. Check Neon or ID.")
