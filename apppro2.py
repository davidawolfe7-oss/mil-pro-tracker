import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. DATABASE SETUP ---
conn = sqlite3.connect('milpro_v9_fleet_fix.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, vehicle TEXT, 
              start_odo REAL, end_odo REAL, dist REAL, type TEXT, details TEXT, savings REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

# IRS 2026 RATES
RATES = {"Business": 0.725, "Medical": 0.22, "Charity": 0.14, "Personal": 0.0}

# --- 2. DARK TACTICAL THEME ---
st.set_page_config(page_title="Mil-Pro Night Ops", layout="wide", page_icon="🇺🇸")

st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        background-image: linear-gradient(rgba(14, 17, 23, 0.9), rgba(14, 17, 23, 0.9)), 
            url('https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg');
        background-attachment: fixed;
        background-size: cover;
        color: #ffffff;
    }
    section[data-testid="stSidebar"] { background-color: #1a1c24 !important; }
    h1, h2, h3, p, label, .stSelectbox label { color: #ffffff !important; font-weight: bold !important; }
    
    /* Vehicle Selector Styling */
    div[data-baseweb="select"] { background-color: #1f2937 !important; border-radius: 5px; }
    
    [data-testid="stMetric"] {
        background-color: #1f2937;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #3b82f6;
    }
    [data-testid="stMetricValue"] { color: #3b82f6 !important; }
    
    .stButton>button {
        background-color: #1d4ed8 !important;
        color: white !important;
        font-weight: bold;
        width: 100%;
    }
    </style>
    
    <div style="text-align: center; padding-bottom: 20px;">
        <h1 style="font-size: 2.5rem; margin-bottom: 0;">🦅 MIL-PRO COMMAND</h1>
        <p style="letter-spacing: 2px; color: #3b82f6;">FLEET & LOGISTICS DASHBOARD</p>
    </div>
    """, unsafe_allow_html=True)

# --- 3. SESSION STATE & NAVIGATION ---
if 'page' not in st.session_state:
    st.session_state.page = 'main'

# --- 4. SIDEBAR: FLEET CONTROL ---
with st.sidebar:
    st.header("🚘 Fleet Status")
    garage_df = pd.read_sql("SELECT * FROM garage", conn)
    
    if not garage_df.empty:
        # THE FIX: Explicitly assigning the selection to a variable we use in the app
        fleet_list = garage_df['name'].tolist()
        active_v = st.selectbox("SELECT ACTIVE VEHICLE", fleet_list, index=0)
        
        v_mpg = garage_df[garage_df['name'] == active_v]['mpg'].values[0]
        st.success(f"ONLINE: {active_v} ({v_mpg} MPG)")
        
        if st.button("🗑️ Decommission Vehicle"):
            c.execute("DELETE FROM garage WHERE name=?", (active_v,))
            conn.commit()
            st.rerun()
    else:
        st.warning("NO VEHICLES DETECTED")
        active_v = None

    st.divider()
    with st.expander("➕ Register New Vehicle"):
        nv_name = st.text_input("Vehicle Name")
        nv_mpg = st.number_input("Vehicle MPG", min_value=1.0, value=20.0)
        if st.button("Add to Fleet"):
            try:
                c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (nv_name, nv_mpg))
                conn.commit()
                st.rerun()
            except: st.error("Name already in use.")

# --- 5. MAIN CONTENT ---
if st.session_state.page == 'main':
    tab1, tab2, tab3 = st.tabs(["🚀 Mission Log", "🎖️ IDT Tactical", "📊 Executive Report"])

    # --- TAB 1: MISSION LOG ---
    with tab1:
        if active_v:
            # Fetch last odometer for THE ACTIVE VEHICLE
            last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{active_v}' ORDER BY id DESC LIMIT 1", conn)
            last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
            
            st.subheader(f"Unit: {active_v}")
            c1, c2 = st.columns(2)
            with c1:
                s_odo = st.number_input("Start Odometer", value=last_val)
                if s_odo > last_val and last_val > 0:
                    st.error(f"🚨 GAP: {s_odo - last_val} miles since last log.")
                    if st.button("Log Gap as Personal"):
                        c.execute("INSERT INTO trips (date, vehicle, dist, type, savings) VALUES (?,?,?,?,?)",
                                  (datetime.date.today(), active_v, s_odo-last_val, "Personal Gap", 0))
                        conn.commit()
                        st.rerun()
            with c2:
                e_odo = st.number_input("End Odometer", value=s_odo + 10.0)
                cat = st.selectbox("Mission Category", ["Business", "Medical", "Charity", "Personal"])

            if st.button("🏁 Finalize & Secure Log", use_container_width=True):
                dist = e_odo - s_odo
                val = dist * RATES.get(cat, 0.0)
                c.execute("INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, savings) VALUES (?,?,?,?,?,?,?)",
                          (datetime.date.today(), active_v, s_odo, e_odo, dist, cat, val))
                conn.commit()
                st.success(f"MISSION SECURE. Tax Credit: ${val:.2f}")
                st.balloons()
        else:
            st.info("Please register a vehicle in the sidebar to begin tracking.")

    # --- TAB 2: IDT TACTICAL ---
    with tab2:
        st.subheader("🎖️ IDT Travel & Logistics")
        mode = st.radio("Logistics Mode", ["POV (Self Drive)", "Flight / Commercial", "Rental Unit"], horizontal=True)
        
        col1, col2 = st.columns(2)
        with col1:
            idt_date = st.date_input("Orders Date", datetime.date.today())
            gas = st.number_input("Fuel/Gas ($)", min_value=0.0)
            tolls = st.number_input("Tolls ($)", min_value=0.0)
            parking = st.number_input("Parking / Airport Fees ($)", min_value=0.0)
        
        with col2:
            reimb = st.number_input("Gov Reimbursement (DTS) ($)", min_value=0.0)
            if mode == "POV (Self Drive)":
                miles = st.number_input("Total Trip Miles (POV)", min_value=0.0)
                total_cost = (miles * 0.725) + gas + tolls + parking
            elif mode == "Flight / Commercial":
                f_cost = st.number_input("Flight Ticket Price ($)", min_value=0.0)
                apt_miles = st.number_input("Miles to Airport (Home POV)", min_value=0.0)
                dest_travel = st.number_input("Destination Rental/Uber ($)", min_value=0.0)
                total_cost = f_cost + (apt_miles * 0.725) + dest_travel + tolls + parking
            else:
                r_cost = st.number_input("Rental Base Price ($)", min_value=0.0)
                total_cost = r_cost + gas + tolls + parking

        net_deduction = max(0.0, total_cost - reimb)
        st.divider()
        st.metric("NET UNREIMBURSED BENEFIT", f"${net_deduction:.2f}")

        if st.button("🎖️ Save IDT Record", use_container_width=True):
            details = f"Mode: {mode} | Costs: G:${gas} T:${tolls} P:${parking}"
            c.execute("INSERT INTO trips (date, vehicle, dist, type, details, savings) VALUES (?,?,?,?,?,?)",
                      (idt_date, "IDT-TACTICAL", 0, "Military IDT", details, net_deduction))
            conn.commit()
            st.success("IDT Logged Successfully.")

    # --- TAB 3: EXECUTIVE REPORT ---
    with tab3:
        st.subheader("📊 Fleet Performance & Financials")
        df = pd.read_sql("SELECT date, vehicle, dist as miles, type, details, savings FROM trips", conn)
        
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            if st.button("🛠️ Prepare Final Export"):
                st.session_state.page = 'download'
                st.rerun()
        else:
            st.info("No mission data found.")

# --- 6. DOWNLOAD PAGE ---
else:
    st.subheader("📩 Tactical Export Ready")
    df_export = pd.read_sql("SELECT date, vehicle, start_odo, end_odo, dist as miles, type, details, savings FROM trips", conn)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Tax_Report')
        workbook = writer.book
        worksheet = writer.sheets['Tax_Report']
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1d4ed8', 'font_color': 'white', 'border': 1})
        for col_num, value in enumerate(df_export.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 18)
        
    st.download_button(
        label="💾 Download Official 2026 Spreadsheet",
        data=output.getvalue(),
        file_name=f"Tactical_Tax_Report_{datetime.date.today()}.xlsx",
        mime="application/vnd.ms-excel",
        use_container_width=True
    )
    
    if st.button("🔙 Return to Command Dash"):
        st.session_state.page = 'main'
        st.rerun()
