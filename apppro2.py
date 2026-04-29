import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- DATABASE SETUP ---
conn = sqlite3.connect('milpro_final.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY, date TEXT, vehicle TEXT, start_odo REAL, end_odo REAL, 
              dist REAL, type TEXT, mode TEXT, fuel_cost REAL, refuels INTEGER, savings REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

def save_trip(date, vehicle, start, end, t_type, mode, fuel_cost, refuels, savings):
    dist = end - start if end > start else 0
    c.execute("""INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, mode, fuel_cost, refuels, savings) 
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (date, vehicle, start, end, dist, t_type, mode, fuel_cost, refuels, savings))
    conn.commit()

# --- APP CONFIG ---
st.set_page_config(page_title="Mil-Pro Logistics", layout="wide", page_icon="🎖️")
st.title("🎖️ Mil-Pro Logistics & Mileage")

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
tab1, tab2, tab3, tab4 = st.tabs(["🚗 Standard Log", "✈️ IDT / Military", "📅 History", "💎 Executive Report"])

# --- TAB 1: STANDARD LOG ---
with tab1:
    if selected_v:
        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("Trip Details")
            date = st.date_input("Date", datetime.date.today())
            cat = st.selectbox("Category", ["Business", "Medical", "Charity", "Personal"])
            
            # Auto-Odometer
            last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
            last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
            
            s_odo = st.number_input("Start Odometer", value=last_val)
            e_odo = st.number_input("End Odometer", value=s_odo + 1.0)
        
        with col_r:
            st.subheader("Fuel & Math")
            gas_p = st.number_input("Price/Gal", value=3.50)
            refuels = st.number_input("Refuel Stops", min_value=0, step=1)
            
            dist = e_odo - s_odo
            fuel_burn = (dist / current_mpg) * gas_p
            # IRS rates 2024-2026: Business .67, Med/Move .21, Charity .14
            rates = {"Business": 0.67, "Medical": 0.21, "Charity": 0.14, "Personal": 0.0}
            deduction = dist * rates.get(cat, 0)
            
            st.metric("Estimated Fuel Spend", f"${fuel_burn:.2f}")
            st.metric("Tax Deduction", f"${deduction:.2f}")

        if st.button("🚀 Finalize Standard Trip", use_container_width=True):
            save_trip(date, selected_v, s_odo, e_odo, cat, "Ground", fuel_burn, refuels, deduction)
            st.success("Logged!")
            st.rerun()

# --- TAB 2: IDT MILITARY ---
with tab2:
    if selected_v:
        st.subheader("Military IDT / Duty Travel")
        mode = st.radio("Travel Mode", ["Personal Car (POV)", "Rental Car", "Flight"], horizontal=True)
        
        c1, c2 = st.columns(2)
        with c1:
            idt_date = st.date_input("Duty Date", datetime.date.today(), key="idt_d")
            dist_ow = st.number_input("One-Way Distance", value=50.0)
            is_rt = st.checkbox("Round Trip", value=True)
        with c2:
            gas_idt = st.number_input("Gas Price/Gal", value=3.50, key="idt_g")
            idt_refuels = st.number_input("Refuel Stops", value=0, key="idt_r")
        
        total_m = dist_ow * 2 if is_rt else dist_ow
        fuel_idt = (total_m / current_mpg) * gas_idt if mode != "Flight" else 0.0
        # GSA POV rate is usually same as Business
        savings_idt = total_m * 0.67 if mode == "Personal Car (POV)" else 0.0
        
        st.info(f"Summary: {mode} covering {total_m} miles. Fuel: ${fuel_idt:.2f}")
        
        if st.button("🎖️ Log IDT Travel", use_container_width=True):
            save_trip(idt_date, selected_v, 0, total_m, "IDT Military", mode, fuel_idt, idt_refuels, savings_idt)
            st.success("IDT Recorded!")

# --- TAB 3: HISTORY ---
with tab3:
    st.subheader("Master Log")
    history = pd.read_sql("SELECT * FROM trips ORDER BY id DESC", conn)
    st.dataframe(history, use_container_width=True)

# --- TAB 4: EXECUTIVE REPORT ---
with tab4:
    st.header("💎 Financial Summary")
    df = pd.read_sql("SELECT * FROM trips", conn)
    
    if not df.empty:
        # Wow Factor Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Miles", f"{df['dist'].sum():,.1f}")
        m2.metric("Total Deductions", f"${df['savings'].sum():,.2f}", delta="Tax Savings")
        m3.metric("Fuel Spend", f"${df['fuel_cost'].sum():,.2f}", delta_color="inverse")
        m4.metric("Refuels", int(df['refuels'].sum()))
        
        st.divider()
        
        # Breakdown by Category
        st.subheader("Savings by Category")
        cat_breakdown = df.groupby('type')['savings'].sum()
        st.bar_chart(cat_breakdown)
        
        # Professional Export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Trips', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Trips']
            # Table formatting
            (max_row, max_col) = df.shape
            column_settings = [{'header': column} for column in df.columns]
            worksheet.add_table(0, 0, max_row, max_col - 1, {'columns': column_settings, 'style': 'Table Style Medium 9'})
        
        st.download_button(
            label="🚀 DOWNLOAD PROFESSIONAL EXCEL REPORT",
            data=buffer.getvalue(),
            file_name=f"MilPro_Financials_{datetime.date.today()}.xlsx",
            mime="application/vnd.ms-excel",
            use_container_width=True
        )
    else:
        st.info("Log your first trip to generate the Executive Report.")
