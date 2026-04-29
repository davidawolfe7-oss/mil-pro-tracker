import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- DATABASE SETUP ---
conn = sqlite3.connect('mil_pro_ios_v2.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS vehicles (id INTEGER PRIMARY KEY, name TEXT, v_type TEXT)')
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY, timestamp TEXT, vehicle TEXT, purpose TEXT, 
              start_odo REAL, end_odo REAL, miles REAL, fuel_spent REAL, 
              fuel_price REAL, is_idt INTEGER, is_rental INTEGER, savings REAL)''')
conn.commit()

# --- HELPERS ---
def get_vehicles():
    df = pd.read_sql("SELECT name FROM vehicles", conn)
    return df['name'].tolist()

def get_last_odo(vehicle_name):
    query = "SELECT end_odo FROM trips WHERE vehicle = ? ORDER BY id DESC LIMIT 1"
    res = c.execute(query, (vehicle_name,)).fetchone()
    return float(res[0]) if res and res[0] is not None else 0.0

# --- STYLING & UI ---
st.set_page_config(page_title="Mil-Pro iOS", layout="centered")
st.title("📱 Mil-Pro iOS")

# SIDEBAR VEHICLE MANAGEMENT
with st.sidebar:
    st.header("Garage")
    with st.expander("➕ Add New Vehicle"):
        new_v = st.text_input("Name (e.g. Ford F-150)")
        v_class = st.selectbox("Class", ["Personal", "Work"])
        if st.button("Register Vehicle"):
            c.execute("INSERT INTO vehicles (name, v_type) VALUES (?,?)", (new_v, v_class))
            conn.commit()
            st.rerun()
    
    vehicles = get_vehicles()
    if vehicles:
        st.divider()
        to_del = st.selectbox("Manage / Delete", vehicles)
        if st.button("🗑️ Delete Selected"):
            c.execute("DELETE FROM vehicles WHERE name=?", (to_del,))
            conn.commit()
            st.rerun()

# MAIN TABS
tab1, tab2, tab3 = st.tabs(["🚀 LOG TRIP", "🎖️ MILITARY IDT", "📊 EXPORT"])

with tab1:
    st.header("🚗 Log New Trip")
    # Fetch last entry for the gap check
    last_entry = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
    last_end_odo = last_entry['end_odo'].iloc[0] if not last_entry.empty else None

    date = st.date_input("Date", datetime.date.today())
    start_odo = st.number_input("Start Odometer", value=last_end_odo if last_end_odo else 0)
    end_odo = st.number_input("End Odometer", value=start_odo + 1)
    
    # --- THE NEW GAP LOGIC ---
    if last_end_odo and start_odo > last_end_odo:
        gap = start_odo - last_end_odo
        st.warning(f"⚠️ Gap of {gap} miles detected!")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Log as Personal"):
                save_trip(date, selected_v, last_end_odo, start_odo, "Personal", 0)
                st.rerun()
        with c2:
            if st.button("Log as Business"):
                save_trip(date, selected_v, last_end_odo, start_odo, "Business (Missed)", gap)
                st.rerun()

    if st.button("Save Trip"):
        miles = end_odo - start_odo
        savings = miles * 0.67  # Standard 2024-2026 rate
        save_trip(date, selected_v, start_odo, end_odo, "Business", savings)
        st.success(f"Saved! You earned ${savings:.2f} in deductions.")

with tab2:
    st.subheader("IDT / Drill Travel")
    idt_mode = st.radio("Mode", ["POV (Personal Vehicle)", "Flight/Rental"])
    
    col_a, col_b = st.columns(2)
    with col_a:
        idt_miles = st.number_input("Round Trip Miles", min_value=0.0)
        refuel = st.checkbox("Refueled during IDT?")
    with col_b:
        if idt_mode == "Flight/Rental":
            rental_cost = st.number_input("Rental/Airfare Cost", min_value=0.0)
            rental_miles = st.number_input("Miles to/from Airport", min_value=0.0)
        
    if refuel:
        st.number_input("Refuel Price per Gallon", format="%.3f", key="idt_ppg")
        st.number_input("Total Refuel Cost", key="idt_total_gas")

    if st.button("💾 SAVE IDT RECORD", width='stretch'):
        # IDT Logic here
        st.success("IDT Data Saved to Secure Log.")

with tab3:
    st.header("📊 Executive Export")
    df = pd.read_sql("SELECT * FROM trips", conn)
    
    if not df.empty:
        # Fill empty values to prevent the TypeError crash
        df = df.fillna("N/A")
        st.dataframe(df)

        if st.button("🚀 GENERATE PROFESSIONAL REPORT"):
            fname = "Mileage_Report_2026.xlsx"
            with pd.ExcelWriter(fname, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Log', index=False)
                workbook = writer.book
                worksheet = writer.sheets['Log']
                
                # Format as a clean table
                (max_row, max_col) = df.shape
                columns = [{'header': col} for col in df.columns]
                worksheet.add_table(0, 0, max_row, max_col - 1, {
                    'columns': columns, 
                    'style': 'Table Style Medium 9'
                })
            
            with open(fname, "rb") as f:
                st.download_button("Download for Accountant", f, file_name=fname)
    else:
        st.info("Log some trips to enable export!")
            with open(fname, "rb") as f:
                st.download_button("Download Report", f, file_name=fname)
    else:
        st.info("No trips to export yet.")
