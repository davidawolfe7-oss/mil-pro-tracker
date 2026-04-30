import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- DATABASE & THEME SETUP ---
conn = sqlite3.connect('milpro_tactical_v1.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY, date TEXT, vehicle TEXT, start_odo REAL, end_odo REAL, 
              dist REAL, type TEXT, fuel_spent REAL, refuels INTEGER, savings REAL, actual_expense REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY, name TEXT, mpg REAL, is_low_mpg INTEGER)''')
conn.commit()

# 2026 IRS RATES
RATES = {"Business": 0.725, "Medical": 0.22, "Charity": 0.14, "Personal": 0.0}

st.set_page_config(page_title="Mil-Pro Tactical Tracker", layout="wide")

# --- CUSTOM CSS FOR MILITARY THEME ---
st.markdown("""
    <style>
    .main {
        background-color: #f0f2f6;
        border-top: 10px solid #002868; /* Old Glory Blue */
    }
    .stButton>button {
        background-color: #002868;
        color: white;
        border-radius: 5px;
    }
    </style>
    <h1 style='text-align: center;'>🇺🇸 Mil-Pro Tactical Tax Tracker 🇺🇸</h1>
    """, unsafe_allow_888)

# --- SIDEBAR: GARAGE & VEHICLE INTEL ---
with st.sidebar:
    st.header("📋 Tactical Garage")
    with st.expander("➕ Add Vehicle"):
        name = st.text_input("Vehicle Name")
        mpg = st.number_input("MPG", min_value=1.0, value=15.0)
        if st.button("Register Vehicle"):
            low_mpg = 1 if mpg < 18 else 0 # Flag for Actual Expense logic
            c.execute("INSERT INTO garage (name, mpg, is_low_mpg) VALUES (?,?,?)", (name, mpg, low_mpg))
            conn.commit()
            st.rerun()

    garage_df = pd.read_sql("SELECT * FROM garage", conn)
    if not garage_df.empty:
        selected_v = st.selectbox("Select Active Vehicle", garage_df['name'].tolist())
        v_data = garage_df[garage_df['name'] == selected_v].iloc[0]
        if v_data['is_low_mpg']:
            st.warning("⚠️ Low MPG Detected. App is tracking 'Actual Expenses' for higher tax refund potential.")
        if st.button("🗑️ Retirement (Delete)"):
            c.execute("DELETE FROM garage WHERE name=?", (selected_v,))
            conn.commit()
            st.rerun()
    else:
        selected_v = None

# --- MAIN TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Mission Log (GPS)", "🎖️ IDT Tactical", "📊 Executive Report"])

# --- TAB 1: MISSION LOG ---
with tab1:
    if selected_v:
        # GPS Gap Detection
        last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
        last_odo = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
        
        st.subheader("Current Sortie")
        col1, col2 = st.columns(2)
        with col1:
            start_odo = st.number_input("Start Odometer (GPS Sync)", value=last_odo)
            if start_odo > last_odo and last_odo > 0:
                gap = start_odo - last_odo
                st.error(f"🚨 GAP DETECTED: {gap} miles missing since last mission.")
                gap_type = st.selectbox("Classify Gap Miles", ["Business", "Medical", "Charity", "Personal"])
                if st.button("Reconcile Gap"):
                    save_val = gap * RATES.get(gap_type, 0)
                    c.execute("INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, savings) VALUES (?,?,?,?,?,?,?)",
                              (datetime.date.today(), selected_v, last_odo, start_odo, gap, gap_type, save_val))
                    conn.commit()
                    st.rerun()
        
        with col2:
            end_odo = st.number_input("End Odometer", value=start_odo + 1.0)
            t_type = st.selectbox("Mission Category", ["Business", "Medical", "Charity", "Personal"])

        st.divider()
        st.subheader("⛽ Fuel Log")
        refuel = st.checkbox("Did you refuel during this trip?")
        fuel_price = 0.0
        if refuel:
            fuel_price = st.number_input("Cost of Fuel ($ Total)", min_value=0.0)

        if st.button("🚩 End Trip & Finalize Log", use_container_width=True):
            dist = end_odo - start_odo
            deduction = dist * RATES.get(t_type, 0)
            # Actual Expense Logic (Gas + Depreciation placeholder)
            actual = fuel_price + (dist * 0.20) 
            
            c.execute("""INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, fuel_spent, refuels, savings, actual_expense) 
                         VALUES (?,?,?,?,?,?,?,?,?,?)""",
                      (datetime.date.today(), selected_v, start_odo, end_odo, dist, t_type, fuel_price, 1 if refuel else 0, deduction, actual))
            conn.commit()
            st.toast(f"Trip Saved! You earned ${deduction:.2f} in tax deductions.")
            st.rerun()

# --- TAB 2: IDT TACTICAL ---
with tab2:
    st.subheader("Military IDT & Duty Deployment")
    st.info("Log your travel to Drill/Orders. We calculate what the military doesn't pay.")
    
    idt_col1, idt_col2 = st.columns(2)
    with idt_col1:
        idt_date = st.date_input("Orders Date", datetime.date.today())
        idt_mode = st.radio("Transport", ["POV (Personal)", "Rental", "Flight"])
        dist_ow = st.number_input("Distance to Unit (One Way)", value=50.0)
        reimbursement = st.number_input("Expected Travel Pay (GSA/DTS) ($)", value=0.0)
    
    with idt_col2:
        idt_refuel = st.number_input("Fuel Cost for IDT Trip ($)", value=0.0)
        other_costs = st.number_input("Parking/Tolls/Misc ($)", value=0.0)

    total_dist = dist_ow * 2
    irs_val = total_dist * 0.725
    total_out_of_pocket = idt_refuel + other_costs
    
    # The Tax Win:
    excess_deduction = max(0, (irs_val + total_out_of_pocket) - reimbursement)
    
    st.metric("Potential Unreimbursed Tax Deduction", f"${excess_deduction:.2f}")
    if st.button("🎖️ Save IDT Log"):
        c.execute("INSERT INTO trips (date, vehicle, dist, type, mode, savings) VALUES (?,?,?,?,?,?)",
                  (idt_date, "IDT", total_dist, "Military IDT", idt_mode, excess_deduction))
        conn.commit()
        st.success("Military Travel Logged.")

# --- TAB 3: EXECUTIVE REPORT ---
with tab3:
    st.header("📊 Accountant-Ready Financials")
    df = pd.read_sql("SELECT * FROM trips", conn)
    
    if not df.empty:
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Mileage Deduction", f"${df['savings'].sum():,.2f}")
        col_m2.metric("Total Fuel Spend", f"${df['fuel_spent'].sum():,.2f}")
        col_m3.metric("Total Miles Logged", f"{df['dist'].sum():,.1f}")

        st.divider()
        st.subheader("Trip History")
        st.dataframe(df, use_container_width=True)

        # THE SPREADSHEET EXPORT
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Tax_Logs_2026', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Tax_Logs_2026']
            # Add a bit of professional styling
            header_format = workbook.add_format({'bold': True, 'bg_color': '#002868', 'font_color': 'white'})
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
        
        st.download_button("📩 Download Professional Spreadsheet for Accountant", 
                           data=buf.getvalue(), 
                           file_name=f"MilPro_Tax_Report_{datetime.date.today()}.xlsx",
                           use_container_width=True)
