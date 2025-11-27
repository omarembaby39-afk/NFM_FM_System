import os
from datetime import datetime, date

import pandas as pd
import streamlit as st

from database_pg import fetch_all, execute
from config import BUILDING_PHOTO_DIR


def _ensure_table():
    execute(
        """
        CREATE TABLE IF NOT EXISTS building_inspections (
            id SERIAL PRIMARY KEY,
            building_id INTEGER REFERENCES buildings(id) ON DELETE CASCADE,
            inspected_at TIMESTAMP NOT NULL,
            inspector_name TEXT,
            cleanliness_rating INTEGER,
            safety_rating INTEGER,
            maintenance_rating INTEGER,
            comments TEXT,
            photo_path TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        (),
    )


def _load_buildings():
    rows = fetch_all("SELECT id, name FROM buildings ORDER BY name")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _load_inspections(limit=50):
    rows = fetch_all(
        """
        SELECT
            bi.id,
            b.name AS building_name,
            bi.inspected_at,
            bi.inspector_name,
            bi.cleanliness_rating,
            bi.safety_rating,
            bi.maintenance_rating,
            bi.comments,
            bi.photo_path
        FROM building_inspections bi
        JOIN buildings b ON bi.building_id = b.id
        ORDER BY bi.inspected_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def render():
    st.title("🏢 Building Inspections")

    _ensure_table()

    df_buildings = _load_buildings()
    if df_buildings.empty:
        st.warning("No buildings found. Please create buildings first.")
        return

    tab1, tab2 = st.tabs(["📝 New Inspection", "📚 Inspection History"])

    # -----------------------
    # Tab 1: New Inspection
    # -----------------------
    with tab1:
        labels_b = df_buildings["name"].tolist()
        sel_b = st.selectbox("Building", labels_b, key="bi_building")
        building_id = int(df_buildings[df_buildings["name"] == sel_b]["id"].iloc[0])

        col1, col2 = st.columns(2)
        with col1:
            inspected_date = st.date_input("Inspection Date", value=date.today(), key="bi_date")
        with col2:
            inspector_name = st.text_input("Inspector Name", key="bi_inspector")

        st.markdown("### Ratings (1–5)")
        c1, c2, c3 = st.columns(3)
        with c1:
            clean_rate = st.slider("Cleanliness", 1, 5, 4, key="bi_clean")
        with c2:
            safety_rate = st.slider("Safety", 1, 5, 4, key="bi_safety")
        with c3:
            maint_rate = st.slider("Maintenance", 1, 5, 4, key="bi_maint")

        comments = st.text_area(
            "Comments / Observations",
            key="bi_comments",
            height=80,
            placeholder="Example: Staircase clean, minor paint damage on level 2, fire extinguisher due next month…",
        )

        photo = st.file_uploader(
            "Attach a Photo (optional)",
            type=["jpg", "jpeg", "png"],
            key="bi_photo",
        )

        if st.button("💾 Save Inspection", type="primary", key="bi_save_btn"):
            os.makedirs(BUILDING_PHOTO_DIR, exist_ok=True)
            photo_path = None
            if photo:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                ext = photo.name.split(".")[-1].lower()
                filename = f"building_{building_id}_{ts}.{ext}"
                full_path = os.path.join(BUILDING_PHOTO_DIR, filename)
                with open(full_path, "wb") as f:
                    f.write(photo.getbuffer())
                photo_path = full_path

            inspected_at = datetime.combine(inspected_date, datetime.now().time())

            ok = execute(
                """
                INSERT INTO building_inspections
                (building_id, inspected_at, inspector_name, cleanliness_rating,
                 safety_rating, maintenance_rating, comments, photo_path)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    building_id,
                    inspected_at,
                    inspector_name.strip(),
                    clean_rate,
                    safety_rate,
                    maint_rate,
                    comments.strip(),
                    photo_path,
                ),
            )
            if ok:
                st.success("Inspection record saved.")
            else:
                st.error("❌ Failed to save inspection.")

    # -----------------------
    # Tab 2: History
    # -----------------------
    with tab2:
        st.subheader("📚 Recent Inspections")

        df_ins = _load_inspections(100)
        if df_ins.empty:
            st.info("No inspections recorded yet.")
            return

        df_view = df_ins.copy()
        df_view["inspected_at"] = pd.to_datetime(df_view["inspected_at"]).dt.strftime("%Y-%m-%d %H:%M")

        st.dataframe(
            df_view[
                [
                    "building_name",
                    "inspected_at",
                    "inspector_name",
                    "cleanliness_rating",
                    "safety_rating",
                    "maintenance_rating",
                    "comments",
                ]
            ],
            use_container_width=True,
        )
