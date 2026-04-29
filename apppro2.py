import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- DATABASE SETUP ---
conn = sqlite3.connect('mileage_pro.db', check_same_thread=False)
c = conn.cursor()
# Updated table to include fuel data and trip categories
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY, date TEXT, vehicle TEXT, start_odo REAL, end_odo REAL, 
              dist REAL, type TEXT, fuel_cost REAL, savings REAL)''')
# Table for Garage
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

# --- HELPER FUNCTIONS ---
def save_trip(date, vehicle, start, end, t_type, fuel_cost, savings):
    dist = end - start
    c.execute("INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, fuel_cost, savings) VALUES (?,?,?,?,?,?,?,?)",
              (date, vehicle, start, end, dist, t_type, fuel_cost, savings))
    conn.commit()

# --- APP INTERFACE ---
st.set_page_config(page_title="Mil-Pro Mileage", layout="centered")
st.title("🎖️ Mil-Pro Tracker Pro")

# --- SIDEBAR: SMART GARAGE ---
with st.sidebar:
    st.header("🚘 Garage Management")
    
    # Add Vehicle
    with st.expander("Add New Vehicle"):
        new_v_name = st.text_input("Vehicle Name (e.g., Silverado)")
        new_v_mpg = st.number_input("Vehicle MPG", min_value=1.0, value=18.0)
        if st.button("Add to Garage"):
            try:
                c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (new_v_name, new_v_mpg))
                conn.commit()
                st.success("Vehicle Added!")
                st.rerun()
            except:
                st.error("Vehicle already exists.")

    # List/Delete Vehicles
    st.divider()
    garage_data = pd.read_sql("SELECT * FROM garage", conn)
    if not garage_data.empty:
        selected_v = st.selectbox("Current Vehicle", garage_data['name'].tolist())
        current_mpg = garage_data[garage_data['name'] == selected_v]['mpg'].values[0]
        st.info(f"Efficiency: {current_mpg} MPG")
        
        if st.button("🗑️ Delete Selected Vehicle"):
            c.execute("DELETE FROM garage WHERE name=?", (selected_v,))
            conn.commit()
            st.rerun()
    else:
        st.warning("Please add a vehicle first.")
        selected_v = None

# --- MAIN TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🚗 Standard Log", "🎖️ IDT Log", "📅 History", "📊 Export"])

# --- TAB 1: STANDARD LOG ---
with tab1:
    if selected_v:
        st.header(f"Logging: {selected_v}")
        
        # Auto-fetch last odometer
        last_entry = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
        last_odo = float(last_entry['end_odo'].iloc[0]) if not last_entry.empty else 0.0

        date = st.date_input("Date", datetime.date.today(), key="std_date")
        start_odo = st.number_input("Start Odometer", value=last_odo, key="std_start")
        end_odo = st.number_input("End Odometer", value=start_odo + 1.0, key="std_end")
        gas_price = st.number_input("Current Gas Price ($/gal)", value=3.50)

        # Calculations
        dist = end_odo - start_odo
        est_fuel_cost = (dist / current_mpg) * gas_price
        tax_deduction = dist * 0.67

        st.metric("Trip Distance", f"{dist:.1f} miles")
        st.metric("Est. Fuel Cost", f"${est_fuel_cost:.2f}")

        if st.button("Save Business Trip"):
            save_trip(date, selected_v, start_odo, end_odo, "Business", est_fuel_cost, tax_deduction)
            st.success("Trip Logged!")
            st.rerun()
    else:
        st.error("Open Sidebar to add a vehicle.")

# --- TAB 2: IDT LOG (Military) ---
with tab2:
    if selected_v:
        st.header("Military IDT Travel")
        st.caption("Calculate travel to/from Drill or Duty.")
        
        idt_date = st.date_input("Duty Date", datetime.date.today(), key="idt_date")
        one_way = st.number_input("One-Way Distance (Miles)", min_value=0.0, value=50.0)
        round_trip = st.checkbox("Round Trip", value=True)
        gas_price_idt = st.number_input("Gas Price ($/gal)", value=3.50, key="idt_gas")
        
        total_miles = one_way * 2 if round_trip else one_way
        actual_fuel_spend = (total_miles / current_mpg) * gas_price_idt
        govt_rate_val = total_miles * 0.67

        col1, col2 = st.columns(2)
        col1.metric("Total Miles", f"{total_miles}")
        col2.metric("Fuel Expense", f"${actual_fuel_spend:.2f}")

        if st.button("Log IDT Trip"):
            # For IDT, we log it as a special type
            save_trip(idt_date, selected_v, 0, total_miles, "IDT Military", actual_fuel_spend, govt_rate_val)
            st.success("Military IDT Logged!")
    else:
        st.info("Select a vehicle in the sidebar.")

# --- TAB 3: HISTORY ---
with tab3:
    st.header("Complete Log History")
    all_trips = pd.read_sql("SELECT * FROM trips ORDER BY id DESC", conn)
    st.dataframe(all_trips)

# --- TAB 4: EXPORT ---
with tab4:
    st.header("Export Reports")
    if not all_trips.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            all_trips.to_excel(writer, sheet_name='Mileage', index=False)
        
        st.download_button(
            label="📩 Download Excel Report",
            data=buffer.getvalue(),
            file_name=f"MilPro_Report_{datetime.date.today()}.xlsx",
            mime="application/vnd.ms-excel"
        )
