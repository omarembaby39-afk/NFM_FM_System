import streamlit as st
import pandas as pd
from database_pg import fetch_all, execute


def render():
    st.title("🚻 WC Groups – Master Data")

    st.caption(
        "This page manages all WC Groups in Um Qasr Welcome Yard. "
        "Data is stored in Neon PostgreSQL."
    )

    st.markdown("---")

    # 1) LOAD EXISTING GROUPS
    rows = fetch_all("SELECT * FROM wc_groups ORDER BY id ASC")
    df = pd.DataFrame(rows)

    if df.empty:
        st.info("No WC groups found yet. Use the form below to add the first group.")
    else:
        st.subheader("Existing WC Groups")
        show_df = df[["id", "code", "name", "location", "status", "notes"]]
        st.dataframe(show_df, use_container_width=True)

    st.markdown("---")

    # 2) ADD NEW GROUP
    st.subheader("Add New WC Group")

    col1, col2 = st.columns(2)
    with col1:
        code = st.text_input("Group Code", placeholder="e.g. G1")
        name = st.text_input("Group Name", placeholder="e.g. Public WC Row 1")
    with col2:
        location = st.text_input("Location", placeholder="e.g. Gate Area")
        status = st.selectbox("Status", ["Clean", "Needs Work", "Out of Service"], index=0)

    notes = st.text_area("Notes", placeholder="Any comments about this group", height=70)

    if st.button("Save WC Group", type="primary"):
        if not code or not name:
            st.error("Group Code and Group Name are required.")
        else:
            ok = execute(
                """
                INSERT INTO wc_groups (code, name, location, status, notes)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (code.strip(), name.strip(), location.strip(), status, notes.strip()),
            )
            if ok:
                st.success("WC Group saved successfully. Please rerun the app to see it in the table.")
            else:
                st.error("Failed to save WC Group. Check Neon connection or if code is duplicated.")

    # 3) (Optional) simple delete by ID
    st.markdown("---")
    st.subheader("Delete WC Group (by ID)")

    delete_id = st.number_input("WC Group ID to delete", min_value=0, value=0, step=1)

    if st.button("Delete WC Group"):
        if delete_id <= 0:
            st.error("Enter a valid ID.")
        else:
            ok = execute("DELETE FROM wc_groups WHERE id = %s", (int(delete_id),))
            if ok:
                st.success(f"WC Group with ID {delete_id} deleted (if it existed).")
            else:
                st.error("Delete failed. Check Neon or ID.")
