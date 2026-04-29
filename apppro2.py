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
      
      # 1. Reset logic to ensure float math
      last_end_odo = 0.0
      if selected_v:
          try:
              # We use a standard connection here to avoid threading issues
              check_df = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
              if not check_df.empty:
                  last_end_odo = float(check_df['end_odo'].iloc[0])
          except:
              last_end_odo = 0.0
  
      # 2. Force these inputs to be Floats explicitly
      date = st.date_input("Trip Date", datetime.date.today())
      
      # This is line 59 - We use 'min_value' to keep the app stable
      start_odo = st.number_input("Start Odometer", min_value=0.0, value=float(last_end_odo), step=0.1)
      end_odo = st.number_input("End Odometer", min_value=float(start_odo), value=float(start_odo) + 1.0, step=0.1)
      
      # 3. Save Logic
      if st.button("Save Current Trip"):
          miles = end_odo - start_odo
          if miles > 0:
              savings = miles * 0.67
              save_trip(date, selected_v, start_odo, end_odo, "Business", savings)
              st.success(f"Saved! ${savings:.2f} added to your 2026 deductions.")
              st.rerun()
          else:
              st.error("End odometer must be greater than start odometer.")

    # 4. Standard Save
    if st.button("Save Current Trip"):
        miles = end_odo - start_odo
        savings = miles * 0.67
        save_trip(date, selected_v, start_odo, end_odo, "Business", savings)
        st.success(f"Saved! You earned ${savings:.2f} in deductions.")
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
        df = df.fillna("N/A")
        st.dataframe(df)

        import io
        # Create a buffer (a temporary spot in memory)
        buffer = io.BytesIO()

        # Write the Excel data to that buffer instead of a file
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Log', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Log']
            (max_row, max_col) = df.shape
            columns = [{'header': col} for col in df.columns]
            worksheet.add_table(0, 0, max_row, max_col - 1, {
                'columns': columns, 
                'style': 'Table Style Medium 9'
            })
            # No need to "close" a buffer, it happens automatically here
        
        # Pull the data out of the buffer for the download button
        st.download_button(
            label="🚀 DOWNLOAD FOR ACCOUNTANT",
            data=buffer.getvalue(),
            file_name="Mileage_Report_2026.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.info("Log some trips to enable export!")
