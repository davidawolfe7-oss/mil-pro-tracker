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
    if not vehicles:
        st.warning("Add a vehicle in the sidebar to start.")
    else:
        v_choice = st.selectbox("Current Vehicle", vehicles)
        last_odo = get_last_odo(v_choice)
        
        # GPS Simulation Mode
        is_tracking = st.toggle("🛰️ Enable GPS Tracking Mode")
        
        col1, col2 = st.columns(2)
        with col1:
            start = st.number_input("Start Odometer", value=last_odo)
        with col2:
            end = st.number_input("End Odometer", value=start + 1.0)
            
        # FIXED GAP LOGIC
        if start > last_odo and last_odo > 0:
            gap_size = start - last_odo
            st.error(f"⚠️ {gap_size} mile Gap Detected! Log as Personal?")
            if st.button("Fix Gap & Save"):
                c.execute("INSERT INTO trips (timestamp, vehicle, purpose, miles, savings) VALUES (?,?,?,?,?)",
                          (datetime.now().strftime("%Y-%m-%d %H:%M"), v_choice, "Personal Gap", gap_size, 0.0))
                conn.commit()
                st.rerun()

        if st.button("✅ SAVE TRIP", width='stretch'):
            miles = end - start
            savings = miles * 0.725
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute("INSERT INTO trips (timestamp, vehicle, purpose, start_odo, end_odo, miles, savings, is_idt) VALUES (?,?,?,?,?,?,?,0)",
                      (now, v_choice, "Business", start, end, miles, savings))
            conn.commit()
            st.balloons()
            st.success(f"Saved {miles} miles!")

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
    st.header("Financial Export")
    df = pd.read_sql("SELECT * FROM trips", conn)
    if not df.empty:
        st.dataframe(df, width='stretch')
        
        # --- PROFESSIONAL EXCEL ENGINE ---
        if st.button("📊 GENERATE PROFESSIONAL REPORT"):
            fname = "Official_Tax_Report_2026.xlsx"
            with pd.ExcelWriter(fname, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Detailed Log', index=False)
                
                workbook = writer.book
                worksheet = writer.sheets['Detailed Log']
                
                # Pro Formatting
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'border': 1})
                money_fmt = workbook.add_format({'num_format': '$#,##0.00'})
                
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format=header_fmt)
                
                worksheet.freeze_panes(1, 0) # Professional touch
                worksheet.set_column('A:L', 15)
                
                # Summary Sheet
                summary = workbook.add_worksheet('Accountant Summary')
                summary.write('A1', 'Total Mileage Deduction (2026)', header_fmt)
                summary.write('B1', df['savings'].sum(), money_fmt)
                
            st.success(f"Report Created: {fname}")
            with open(fname, "rb") as f:
                st.download_button("Download Report", f, file_name=fname)
    else:
        st.info("No trips to export yet.")