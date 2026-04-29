import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- DATABASE SETUP ---
conn = sqlite3.connect('milpro_tactical.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY, date TEXT, vehicle TEXT, start_odo REAL, end_odo REAL, 
              dist REAL, type TEXT, mode TEXT, fuel_cost REAL, travel_cost REAL, refuels INTEGER, savings REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

def save_trip(date, vehicle, start, end, t_type, mode, fuel, travel, refuels, savings):
    dist = end - start if end > start else 0
    c.execute("""INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, mode, fuel_cost, travel_cost, refuels, savings) 
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
              (date, vehicle, start, end, dist, t_type, mode, fuel, travel, refuels, savings))
    conn.commit()

# --- APP CONFIG ---
st.set_page_config(page_title="Mil-Pro Tactical", layout="wide", page_icon="🎖️")
st.title("🎖️ Mil-Pro Tactical Logistics")

# --- SIDEBAR: GARAGE ---
with st.sidebar:
    st.header("🚘 Garage Management")
    with st.expander("➕ Add Vehicle"):
        nv_name = st.text_input("Name")
        nv_mpg = st.number_input("MPG", min_value=1.0, value=20.0)
        if st.button("Save to Garage"):
            try:
                c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (nv_name, nv_mpg))
                conn.commit()
                st.rerun()
            except: st.error("Exists!")

    st.divider()
    garage_df = pd.read_sql("SELECT * FROM garage", conn)
    if not garage_df.empty:
        selected_v = st.selectbox("Active Vehicle", garage_df['name'].tolist())
        current_mpg = garage_df[garage_df['name'] == selected_v]['mpg'].values[0]
        if st.button("🗑️ Delete Selected"):
            c.execute("DELETE FROM garage WHERE name=?", (selected_v,))
            conn.commit()
            st.rerun()
    else:
        st.warning("Add a vehicle first!")
        selected_v = None

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🚗 Standard Log", "✈️ IDT / Military Pro", "📅 History", "💎 Executive Report"])

# --- TAB 1: STANDARD LOG ---
with tab1:
    if selected_v:
        # GAP DETECTION LOGIC
        last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
        last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
        
        st.subheader("Trip Details")
        date = st.date_input("Date", datetime.date.today())
        cat = st.selectbox("Category", ["Business", "Medical", "Charity", "Personal"])
        
        col1, col2 = st.columns(2)
        with col1:
            s_odo = st.number_input("Start Odometer", value=last_val)
            if s_odo > last_val and last_val != 0:
                gap = s_odo - last_val
                st.warning(f"⚠️ Gap detected: {gap} miles missing!")
                if st.button(f"Log {gap}mi as Personal Gap"):
                    save_trip(date, selected_v, last_val, s_odo, "Personal", "Gap Fill", 0, 0, 0, 0)
                    st.rerun()
        with col2:
            e_odo = st.number_input("End Odometer", value=s_odo + 1.0)
        
        gas_p = st.number_input("Price/Gal", value=3.50)
        dist = e_odo - s_odo
        fuel_burn = (dist / current_mpg) * gas_p
        rates = {"Business": 0.67, "Medical": 0.21, "Charity": 0.14, "Personal": 0.0}
        deduction = dist * rates.get(cat, 0)

        if st.button("🚀 Save Standard Trip", use_container_width=True):
            save_trip(date, selected_v, s_odo, e_odo, cat, "Ground", fuel_burn, 0, 0, deduction)
            st.success("Logged!")
            st.rerun()

# --- TAB 2: IDT MILITARY PRO ---
with tab2:
    if selected_v:
        st.subheader("Tactical IDT Deployment")
        mode = st.radio("Primary Mode", ["Personal Car (POV)", "Rental Car", "Flight"], horizontal=True)
        
        c1, c2 = st.columns(2)
        with c1:
            idt_date = st.date_input("Duty Date", datetime.date.today(), key="idt_d")
            if mode == "Flight":
                flight_cost = st.number_input("Flight Ticket Cost ($)", min_value=0.0)
                rental_at_dest = st.checkbox("Rental Car at Destination?")
                dest_rental_cost = st.number_input("Rental Cost ($)", min_value=0.0) if rental_at_dest else 0.0
            else:
                dist_ow = st.number_input("One-Way Distance", value=50.0)
                is_rt = st.checkbox("Round Trip", value=True)
                rental_cost = st.number_input("Rental Daily Rate/Total ($)", value=0.0) if mode == "Rental Car" else 0.0

        with c2:
            gas_idt = st.number_input("Gas Price/Gal", value=3.50, key="idt_g")
            idt_refuels = st.number_input("Refuel Stops", value=0, key="idt_r")
            if mode == "Flight":
                airport_dist = st.number_input("Miles to Airport (One Way)", value=15.0)
                transit_mode = st.selectbox("Airport Transit Mode", ["POV", "Uber/Taxi", "Rental"])

        # IDT MATH ENGINE
        total_m = (dist_ow * 2 if is_rt else dist_ow) if mode != "Flight" else (airport_dist * 2)
        fuel_idt = (total_m / current_mpg) * gas_idt
        travel_total = (flight_cost + dest_rental_cost) if mode == "Flight" else rental_cost
        
        # Savings: Only POV miles get the IRS rate
        pov_savings = total_m * 0.67 if (mode == "Personal Car (POV)" or (mode == "Flight" and transit_mode == "POV")) else 0.0

        st.divider()
        st.write(f"📊 **Financial Impact:** Fuel: ${fuel_idt:.2f} | Out-of-Pocket: ${travel_total:.2f} | Deduction: ${pov_savings:.2f}")

        if st.button("🎖️ Save IDT Record", use_container_width=True):
            save_trip(idt_date, selected_v, 0, total_m, "IDT Military", mode, fuel_idt, travel_total, idt_refuels, pov_savings)
            st.success("Military Record Finalized!")

# --- TAB 3: HISTORY ---
with tab3:
    st.subheader("Master Tactical Log")
    history = pd.read_sql("SELECT * FROM trips ORDER BY id DESC", conn)
    st.dataframe(history, use_container_width=True)

# --- TAB 4: EXECUTIVE REPORT ---
with tab4:
    st.header("💎 Executive Financial Summary")
    df = pd.read_sql("SELECT * FROM trips", conn)
    
    if not df.empty:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Distance", f"{df['dist'].sum():,.1f} mi")
        m2.metric("Tax Deductions", f"${df['savings'].sum():,.2f}")
        m3.metric("Total Costs", f"${df['fuel_cost'].sum() + df['travel_cost'].sum():,.2f}")
        m4.metric("Refuels", int(df['refuels'].sum()))
        
        st.divider()
        st.subheader("Spending vs. Savings")
        chart_data = pd.DataFrame({
            'Category': ['Fuel', 'Travel (Rentals/Flights)', 'Tax Savings'],
            'Dollars': [df['fuel_cost'].sum(), df['travel_cost'].sum(), df['savings'].sum()]
        })
        st.bar_chart(data=chart_data, x='Category', y='Dollars')

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Detailed_Log', index=False)
        st.download_button("📩 Download Professional Report", data=buffer.getvalue(), file_name="MilPro_Report.xlsx", use_container_width=True)
