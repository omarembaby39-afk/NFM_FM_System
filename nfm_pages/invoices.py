import os
import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

from database_pg import fetch_all, execute
from config import LOCAL_DATA_DIR, INVOICE_FILES_DIR


# ----------------------------------------------------
# Helper: generate invoice number like INV-YYYYMM-001
# ----------------------------------------------------
def generate_invoice_no(year: int, month: int) -> str:
    rows = fetch_all(
        "SELECT invoice_no FROM invoices WHERE year=%s AND month=%s ORDER BY id DESC LIMIT 1",
        (year, month),
    )
    if not rows or not rows[0].get("invoice_no"):
        return f"INV-{year}{month:02d}-001"

    last = rows[0]["invoice_no"]
    try:
        seq = int(last.split("-")[-1])
    except Exception:
        seq = 0
    return f"INV-{year}{month:02d}-{seq+1:03d}"


# ----------------------------------------------------
# Helper: get labour total from attendance + workers
# ----------------------------------------------------
def compute_labour_total(month_start, month_end) -> (float, pd.DataFrame):
    rows = fetch_all(
        """
        SELECT
            w.worker_code,
            w.full_name,
            w.position,
            w.salary,
            COALESCE(SUM(a.hours_worked), 0) AS total_hours,
            COALESCE(SUM(a.overtime_hours), 0) AS total_ot
        FROM workers w
        LEFT JOIN attendance a
            ON w.id = a.worker_id
           AND a.att_date BETWEEN %s AND %s
        WHERE w.status = 'Active'
        GROUP BY w.worker_code, w.full_name, w.position, w.salary
        ORDER BY w.worker_code
        """,
        (month_start, month_end),
    )

    if not rows:
        return 0.0, pd.DataFrame()

    df = pd.DataFrame(rows)

    def compute_row_pay(row):
        salary = float(row.get("salary") or 0)
        if salary <= 0:
            return 0.0, 0.0, 0.0
        # 26 days * 8 hours
        hourly_rate = salary / (26 * 8)
        basic_hours = float(row.get("total_hours") or 0)
        ot_hours = float(row.get("total_ot") or 0)
        basic_pay = hourly_rate * basic_hours
        ot_pay = hourly_rate * ot_hours
        total = basic_pay + ot_pay
        return basic_pay, ot_pay, total

    basic_list = []
    ot_list = []
    total_list = []

    for _, r in df.iterrows():
        b, o, t = compute_row_pay(r)
        basic_list.append(round(b, 0))
        ot_list.append(round(o, 0))
        total_list.append(round(t, 0))

    df["Basic_Pay_Est"] = basic_list
    df["OT_Pay_Est"] = ot_list
    df["Total_Pay_Est"] = total_list

    labour_total = df["Total_Pay_Est"].sum()
    return float(labour_total), df


# ----------------------------------------------------
# Helper: get fleet cost from fleet_timesheet + assets
# ----------------------------------------------------
def compute_fleet_total(month_start, month_end) -> (float, pd.DataFrame):
    rows = fetch_all(
        """
        SELECT
            ft.id,
            ft.used_date,
            ft.hours_used,
            fa.asset_code,
            fa.type,
            fa.hourly_rate,
            (ft.hours_used * fa.hourly_rate) AS cost
        FROM fleet_timesheet ft
        JOIN fleet_assets fa ON ft.asset_id = fa.id
        WHERE ft.used_date BETWEEN %s AND %s
        ORDER BY ft.used_date DESC, ft.id DESC
        """,
        (month_start, month_end),
    )

    if not rows:
        return 0.0, pd.DataFrame()

    df = pd.DataFrame(rows)
    df["cost"] = df["cost"].astype(float)
    fleet_total = df["cost"].sum()
    return float(fleet_total), df


# ----------------------------------------------------
# MAIN PAGE
# ----------------------------------------------------
def render():
    st.title("📑 Monthly FM Invoice – Um Qasr Welcome Yard")

    st.caption(
        "Generate monthly Facility Management invoice combining labour, fleet, "
        "other charges, and 15% (or custom) overhead for the client."
    )

    # -----------------------------
    # Period selection
    # -----------------------------
    today = date.today()
    col1, col2, col3 = st.columns(3)
    with col1:
        year = st.number_input("Year", min_value=2020, max_value=2100, value=today.year, step=1)
    with col2:
        month = st.number_input("Month", min_value=1, max_value=12, value=today.month, step=1)
    with col3:
        overhead_pct = st.number_input(
            "Overhead % (Admin / OH)",
            min_value=0.0,
            max_value=100.0,
            value=15.0,
            step=0.5,
        )

    month_start = date(int(year), int(month), 1)
    month_end = month_start + relativedelta(months=1) - relativedelta(days=1)
    st.markdown(f"**Invoice Period:** {month_start} → {month_end}")

    st.markdown("---")

    # -----------------------------
    # Compute labour & fleet totals
    # -----------------------------
    st.subheader("1️⃣ Auto Calculation")

    with st.spinner("Calculating labour & fleet totals..."):
        labour_total, df_labour = compute_labour_total(month_start, month_end)
        fleet_total, df_fleet = compute_fleet_total(month_start, month_end)

    colk1, colk2 = st.columns(2)
    colk1.metric("Labour Total (IQD)", f"{labour_total:,.0f}")
    colk2.metric("Fleet Total (IQD)", f"{fleet_total:,.0f}")

    st.markdown("You can review details below if needed:")
    with st.expander("Labour details (from Attendance & Workers)"):
        if df_labour.empty:
            st.info("No labour data for this period.")
        else:
            st.dataframe(df_labour, use_container_width=True)

    with st.expander("Fleet usage details (from Fleet Timesheet)"):
        if df_fleet.empty:
            st.info("No fleet data for this period.")
        else:
            st.dataframe(df_fleet, use_container_width=True)

    st.markdown("---")

    # -----------------------------
    # Other charges + overhead
    # -----------------------------
    st.subheader("2️⃣ Other Charges & Overhead")

    colc1, colc2 = st.columns(2)
    with colc1:
        other_total = st.number_input(
            "Other Charges (Materials / Consumables / Tools etc.) – IQD",
            min_value=0.0,
            step=1000.0,
            value=0.0,
        )
    with colc2:
        manual_override = st.checkbox(
            "Allow manual override of labour & fleet totals", value=False
        )

    if manual_override:
        colm1, colm2 = st.columns(2)
        with colm1:
            labour_total = st.number_input(
                "Override Labour Total (IQD)", min_value=0.0, value=labour_total, step=1000.0
            )
        with colm2:
            fleet_total = st.number_input(
                "Override Fleet Total (IQD)", min_value=0.0, value=fleet_total, step=1000.0
            )

    subtotal = labour_total + fleet_total + other_total
    overhead_amount = subtotal * (overhead_pct / 100.0)
    grand_total = subtotal + overhead_amount

    st.markdown("### 3️⃣ Invoice Summary")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Labour (IQD)", f"{labour_total:,.0f}")
    c2.metric("Fleet (IQD)", f"{fleet_total:,.0f}")
    c3.metric("Other (IQD)", f"{other_total:,.0f}")
    c4.metric("Subtotal (IQD)", f"{subtotal:,.0f}")

    c5, c6 = st.columns(2)
    c5.metric("Overhead %", f"{overhead_pct:.1f}%")
    c6.metric("Overhead Amount (IQD)", f"{overhead_amount:,.0f}")

    st.markdown(f"## 💵 Grand Total (IQD): **{grand_total:,.0f}**")

    st.markdown("---")

    # -----------------------------
    # Client / contract info
    # -----------------------------
    st.subheader("4️⃣ Client & Contract Info")

    colinfo1, colinfo2 = st.columns(2)
    with colinfo1:
        client_name = st.text_input(
            "Invoice To (Client Name)",
            value="General Company for Ports of Iraq – Um Qasr Port",
        )
        contract_ref = st.text_input(
            "Contract / PO Reference",
            value="NFM-UMQASR-FM-001",
        )
    with colinfo2:
        notes = st.text_area(
            "Notes on this Invoice",
            placeholder="Scope: Cleaning & Maintenance of Welcome Yard WC groups, Buildings, Fleet operation, etc.",
            height=80,
        )
        invoice_file = st.file_uploader(
            "Upload signed client invoice / support document (PDF / JPG / PNG) – optional",
            type=["pdf", "jpg", "jpeg", "png"],
        )

    st.markdown("---")

    # -----------------------------
    # Save invoice
    # -----------------------------
    if st.button("💾 Save Monthly Invoice to Neon", type="primary"):
        # Generate invoice number
        inv_no = generate_invoice_no(int(year), int(month))

        # Save file if any
        invoice_file_path = None
        if invoice_file is not None:
            try:
                os.makedirs(INVOICE_FILES_DIR, exist_ok=True)
                ext = invoice_file.name.split(".")[-1].lower()
                safe_name = f"{inv_no}.{ext}"
                invoice_file_path = os.path.join(INVOICE_FILES_DIR, safe_name)
                with open(invoice_file_path, "wb") as f:
                    f.write(invoice_file.getbuffer())
            except Exception as e:
                st.warning(f"Could not save invoice file to disk: {e}")
                invoice_file_path = None

        ok = execute(
            """
            INSERT INTO invoices
            (invoice_no, year, month, labour_total, fleet_total, other_total,
             overhead_pct, overhead_amount, grand_total,
             client_name, contract_ref, notes, invoice_file_path)
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                inv_no,
                int(year),
                int(month),
                labour_total,
                fleet_total,
                other_total,
                overhead_pct,
                overhead_amount,
                grand_total,
                client_name.strip(),
                contract_ref.strip(),
                notes.strip(),
                invoice_file_path,
            ),
        )

        if ok:
            st.success(f"Invoice {inv_no} saved successfully to Neon.")
            st.info(
                "You can later use this data for client billing, internal reports, "
                "and monthly revenue summaries."
            )
        else:
            st.error("❌ Failed to save invoice. Check Neon connection & table definition.")

    st.markdown("---")

    # -----------------------------
    # Previous invoices list
    # -----------------------------
    st.subheader("📚 Previous FM Invoices (Last 12)")

    rows_inv = fetch_all(
        """
        SELECT id, invoice_no, year, month,
               labour_total, fleet_total, other_total,
               overhead_pct, overhead_amount, grand_total,
               client_name, contract_ref, created_at
        FROM invoices
        ORDER BY year DESC, month DESC, id DESC
        LIMIT 12
        """
    )

    if not rows_inv:
        st.info("No invoices saved yet.")
    else:
        df_inv = pd.DataFrame(rows_inv)
        st.dataframe(df_inv, use_container_width=True)
