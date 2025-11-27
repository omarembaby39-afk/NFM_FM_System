import os
import json
import streamlit as st

from config import (
    BASE_DIR,
    SETTINGS_FILE,
    LOCAL_DATA_DIR,
    PHOTO_DIR,
    WORKER_PHOTO_DIR,
    BUILDING_PHOTO_DIR,
    WC_PHOTO_DIR,
    FLEET_PHOTO_DIR,
    INVOICE_FILES_DIR,
    NEON_DB_URL,
)


def _mask_neon_url(url: str) -> str:
    """
    Mask Neon URL to avoid showing full password, but keep host info for help.
    Example: postgresql://neondb_owner:****@ep-...aws.neon.tech/neondb
    """
    if "://" not in url:
        return url
    try:
        scheme, rest = url.split("://", 1)
        if "@" not in rest:
            return url
        creds, host_part = rest.split("@", 1)
        if ":" in creds:
            user, _pwd = creds.split(":", 1)
            masked_creds = f"{user}:****"
        else:
            masked_creds = "****"
        return f"{scheme}://{masked_creds}@{host_part}"
    except Exception:
        return url


def render():
    st.title("⚙️ Settings & Help – NFM FM System")

    st.caption(
        "Here you can see system paths, database info, and change the local data folder "
        "used for exports, invoices and reports (for when you move to a new PC or OneDrive path)."
    )

    st.markdown("## ℹ️ System Information")

    col1, col2 = st.columns(2)
    with col1:
        st.write("**App Base Folder:**")
        st.code(str(BASE_DIR), language="text")

        st.write("**Current Local Data Folder (OneDrive):**")
        st.code(str(LOCAL_DATA_DIR), language="text")

        st.write("**Invoices Folder:**")
        st.code(str(INVOICE_FILES_DIR), language="text")

    with col2:
        st.write("**Photos Root Folder:**")
        st.code(str(PHOTO_DIR), language="text")

        st.write("**Worker Photos:**")
        st.code(str(WORKER_PHOTO_DIR), language="text")

        st.write("**WC Photos:**")
        st.code(str(WC_PHOTO_DIR), language="text")

    st.markdown("### 🗄 Database Connection (Neon)")

    st.write("**Type:** PostgreSQL (Neon Cloud)")
    st.write("**Connection (masked):**")
    st.code(_mask_neon_url(NEON_DB_URL), language="text")

    st.info(
        "The Neon URL is stored in `config.py`. If you rotate the password on Neon, "
        "you must update it there (or via NEON_DB_URL environment variable)."
    )

    st.markdown("---")

    # --------------------------------------------
    # Editable Local Data Folder
    # --------------------------------------------
    st.markdown("## 🧩 Local Data Folder (Configurable)")

    st.write(
        "This is the Windows / OneDrive folder where the app saves:\n"
        "- Invoices PDFs\n"
        "- Exported CSV reports\n"
        "- Future FM/HR exports\n\n"
        "If you move to a new PC or change your OneDrive path, update it here."
    )

    new_path = st.text_input(
        "Local Data Folder (OneDrive)",
        value=str(LOCAL_DATA_DIR),
        help="Example: C:\\Users\\acer\\OneDrive\\NilepsHR_Database\\RO-UMQASR",
    )

    if st.button("💾 Save Local Data Folder", type="primary"):
        new_path = new_path.strip()
        if not new_path:
            st.error("Please enter a valid folder path.")
        else:
            try:
                os.makedirs(new_path, exist_ok=True)

                # Load existing settings if any
                data = {}
                if os.path.exists(SETTINGS_FILE):
                    try:
                        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except Exception:
                        data = {}

                data["local_data_dir"] = new_path

                with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                st.success("Local data folder saved to settings.json.")
                st.warning(
                    "Please **restart the Streamlit app** so all modules use the new path."
                )
            except Exception as e:
                st.error(f"❌ Failed to save / create folder: {e}")

    st.markdown("---")

    st.markdown("## ❓ Help / Usage Notes")

    st.markdown(
        """
- **Changing PC / OneDrive path:**
  1. Install Python + venv as usual
  2. Copy the `NFM_FM_System` folder to the new PC
  3. Open this Settings page
  4. Update **Local Data Folder** to the new OneDrive path
  5. Restart the app

- **Database (Neon):**
  - All live data (workers, attendance, WOs, fleet, invoices) is stored in Neon.
  - Local folders (shown above) are only for **exports / PDFs / photos**.

- **Backup recommendation:**
  - Periodically backup the whole `NFM_FM_System` folder.
  - Also export key tables from Neon (workers, attendance, work_orders, fleet_timesheet, invoices).
        """
    )
