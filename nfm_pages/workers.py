import os
import streamlit as st
import pandas as pd
from database_pg import fetch_all, execute
from config import WORKER_PHOTO_DIR, ALLOWED_PHOTO_TYPES


def _load_workers():
    rows = fetch_all(
        """
        SELECT id, worker_code, full_name, nationality, position, visa_expiry,
               status, salary, notes
        FROM workers
        ORDER BY worker_code
        """
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _save_photo(file, worker_code):
    ext = file.name.split(".")[-1].lower()
    if ext not in ALLOWED_PHOTO_TYPES:
        return None

    os.makedirs(WORKER_PHOTO_DIR, exist_ok=True)
    filename = f"{worker_code}.{ext}"
    full_path = os.path.join(WORKER_PHOTO_DIR, filename)

    with open(full_path, "wb") as f:
        f.write(file.getbuffer())

    return full_path


def render():
    st.title("👷 Workers Management")

    st.caption("Add, edit and maintain worker profiles, salaries and photos.")

    df = _load_workers()
    if df.empty:
        st.info("No workers found. Add new workers below.")

    st.markdown("## 📋 Worker List")

    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.markdown("## ➕ Add New Worker")

    col1, col2, col3 = st.columns(3)

    with col1:
        new_code = st.text_input("Worker Code", key="new_worker_code")
        new_name = st.text_input("Full Name", key="new_worker_name")

    with col2:
        new_nat = st.selectbox(
            "Nationality",
            ["Egyptian", "Iraqi", "Other"],
            key="new_worker_nat"
        )

        new_position = st.selectbox(
            "Position",
            ["Worker", "Supervisor", "Engineer"],
            key="new_worker_position"
        )

    with col3:
        new_salary = st.number_input(
            "Basic Salary", min_value=0, value=0, step=10, key="new_worker_salary"
        )
        new_status = st.selectbox(
            "Status",
            ["Active", "Inactive"],
            key="new_worker_status"
        )

    new_visa = st.date_input(
        "Visa Expiry (if foreign)",
        key="new_worker_visa"
    )

    new_notes = st.text_area(
        "Notes",
        key="new_worker_notes",
        height=60
    )

    new_photo = st.file_uploader(
        "Upload Photo",
        type=["jpg", "jpeg", "png"],
        key="new_worker_photo"
    )

    if st.button("💾 Save New Worker", type="primary", key="btn_save_new_worker"):
        if not new_code or not new_name:
            st.error("Worker code and name are required.")
        else:
            ok = execute(
                """
                INSERT INTO workers
                (worker_code, full_name, nationality, position, visa_expiry,
                 status, salary, notes, photo_path)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    new_code,
                    new_name,
                    new_nat,
                    new_position,
                    new_visa,
                    new_status,
                    new_salary,
                    new_notes,
                    None,
                ),
            )
            if ok:
                if new_photo:
                    _save_photo(new_photo, new_code)
                st.success("Worker added.")
                st.rerun()
            else:
                st.error("❌ Neon error while adding worker.")

    st.markdown("---")
    st.markdown("## ✏️ Edit Existing Worker")

    if df.empty:
        st.info("No workers to edit.")
        return

    worker_labels = [f"{r.worker_code} – {r.full_name}" for _, r in df.iterrows()]
    worker_map = {lbl: r.id for lbl, (_, r) in zip(worker_labels, df.iterrows())}

    sel_label = st.selectbox(
        "Select Worker",
        worker_labels,
        key="edit_worker_select"
    )
    worker_id = worker_map[sel_label]

    row = df[df["id"] == worker_id].iloc[0]

    col1, col2, col3 = st.columns(3)

    with col1:
        e_code = st.text_input("Worker Code", row["worker_code"], key="edit_worker_code")
        e_name = st.text_input("Full Name", row["full_name"], key="edit_worker_name")

    with col2:
        e_nat = st.selectbox(
            "Nationality",
            ["Egyptian", "Iraqi", "Other"],
            index=["Egyptian", "Iraqi", "Other"].index(row["nationality"]),
            key="edit_worker_nat"
        )

        e_position = st.selectbox(
            "Position",
            ["Worker", "Supervisor", "Engineer"],
            index=["Worker", "Supervisor", "Engineer"].index(row["position"]),
            key="edit_worker_position"     # 🔥 UNIQUE KEY FIXED
        )

    with col3:
        e_salary = st.number_input(
            "Basic Salary", min_value=0, value=int(row["salary"]), step=10,
            key="edit_worker_salary"
        )
        e_status = st.selectbox(
            "Status",
            ["Active", "Inactive"],
            index=["Active", "Inactive"].index(row["status"]),
            key="edit_worker_status"
        )

    e_visa = st.date_input(
        "Visa Expiry",
        row["visa_expiry"],
        key="edit_worker_visa"
    )

    e_notes = st.text_area(
        "Notes",
        value=row["notes"] or "",
        key="edit_worker_notes",
        height=60
    )

    edit_photo = st.file_uploader(
        "Replace Photo (optional)",
        type=["jpg", "jpeg", "png"],
        key="edit_worker_photo"
    )

    if st.button("💾 Update Worker", type="primary", key="btn_update_worker"):
        ok = execute(
            """
            UPDATE workers
            SET worker_code=%s,
                full_name=%s,
                nationality=%s,
                position=%s,
                visa_expiry=%s,
                status=%s,
                salary=%s,
                notes=%s
            WHERE id=%s
            """,
            (
                e_code,
                e_name,
                e_nat,
                e_position,
                e_visa,
                e_status,
                e_salary,
                e_notes,
                worker_id,
            ),
        )
        if ok:
            if edit_photo:
                _save_photo(edit_photo, e_code)
            st.success("Worker updated.")
            st.rerun()
        else:
            st.error("❌ Neon update failed.")

    st.markdown("---")
    st.markdown("## 🗑 Delete Worker")

    if st.button("Delete Worker", type="secondary", key="btn_delete_worker"):
        ok = execute("DELETE FROM workers WHERE id=%s", (worker_id,))
        if ok:
            st.success("Worker deleted.")
            st.rerun()
        else:
            st.error("❌ Neon delete failed.")
