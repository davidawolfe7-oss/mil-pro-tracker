import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. PRO-LEVEL DATABASE INITIALIZATION ---
def initialize_db():
    conn = sqlite3.connect('milpro_command_v20.db', check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    # Create tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS trips 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, vehicle TEXT, 
                  miles REAL, type TEXT, fuel REAL, tolls REAL, lodging REAL, 
                  transit REAL, laundry REAL, reimb REAL, savings REAL, 
                  start_odo REAL, end_odo REAL, notes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS garage 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mpg REAL)''')
    
    # Schema Migration: Add columns if they were missed in previous versions to prevent crash
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(trips)")]
    needed_cols = [('start_odo', 'REAL'), ('end_odo', 'REAL'), ('notes', 'TEXT')]
    for col, col_type in needed_cols:
        if col not in existing_cols:
            c.execute(f"ALTER TABLE trips ADD COLUMN {col} {col_type}")
    
    conn.commit()
    return conn

conn = initialize_db()

# --- 2. THEME & TACTICAL UI ---
st.set_page_config(page_title="Mil-Pro Command", layout="wide", page_icon="🦅")

st.markdown("""
    <style>
    .stApp {
        background-image: linear-gradient(rgba(14, 17, 23, 0.85), rgba(14, 17, 23, 0.85)), 
            url('https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg');
        background-attachment: fixed; background-size: cover; color: #ffffff;
    }
    [data-testid="stMetric"] { background-color: #1f2937; border: 1px solid #3b82f6; border-radius: 10px; }
    .stButton>button { background-color: #1d4ed8 !important; color: white !important; font-weight: bold; width: 100%; height: 3.5em; }
    .return-btn > button { 
        background-color: #B22234 !important; border: 3px solid white !important; 
        height: 5em !important; font-size: 1.2rem !important; margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SESSION STATE MANAGEMENT ---
if 'page' not in st.session_state: st.session_state.page = 'main'
if 'gps_start' not in st.session_state: st.session_state.gps_start = None

def navigate(page_name):
    st.session_state.page = page_name

# --- 4. SIDEBAR: FLEET COMMAND ---
with st.sidebar:
    st.header("🚘 Fleet Status")
    garage_df = pd.read_sql("SELECT * FROM garage ORDER BY name ASC", conn)
    active_v = st.selectbox("ACTIVE VEHICLE", garage_df['name'].tolist()) if not garage_df.empty else None
    
    with st.expander("➕ Register New Unit"):
        new_n = st.text_input("Name (e.g. Ford F-150)")
        new_m = st.number_input("Unit MPG", value=20.0)
        if st.button("Commit to Fleet"):
            if new_n:
                try:
                    conn.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (new_n, new_m))
                    conn.commit()
                    st.success(f"{new_n} Locked.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.info("Unit already exists.")

# --- 5. MAIN DASHBOARD ---
if st.session_state.page == 'main':
    t1, t2, t3 = st.tabs(["🚀 Mission Log", "🎖️ IDT Logistics", "📊 Report"])

    with t1:
        if active_v:
            # 1. Automatic Gap Logic
            last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{active_v}' AND end_odo IS NOT NULL ORDER BY id DESC LIMIT 1", conn)
            last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
            
            st.subheader(f"Unit: {active_v}")
            
            # 2. GPS "Check-In" System
            c_gps1, c_gps2 = st.columns(2)
            with c_gps1:
                if st.button("🛰️ START TRIP GPS"):
                    st.session_state.gps_start = datetime.datetime.now()
                    st.info("Trip Timer Started...")
            with c_gps2:
                if st.session_state.gps_start:
                    if st.button("🛑 END TRIP"):
                        st.session_state.gps_start = None
                        st.success("Trip Ended. Log distance below.")

            st.divider()
            
            # 3. Manual Entry & Gap Detection
            c1, c2, c3 = st.columns(3)
            with c1: m_date = st.date_input("Mission Date", datetime.date.today())
            with c2: s_odo = st.number_input("Start Odometer", value=last_val)
            with c3: e_odo = st.number_input("End Odometer", value=s_odo + 1.0)
            
            if s_odo > last_val and last_val > 0:
                gap = s_odo - last_val
                st.warning(f"🚨 GAP DETECTED: {gap} Miles")
                gap_type = st.selectbox("Assign Gap To:", ["Personal / Unlogged", "Business / Work", "Medical / VA", "Charity"], key="gap_sel")
                if st.button(f"Resolve Gap as {gap_type}"):
                    rate = 0.725 if "Business" in gap_type else (0.22 if "Medical" in gap_type else 0.0)
                    conn.execute("INSERT INTO trips (date, vehicle, miles, type, savings) VALUES (?,?,?,?,?)",
                                 (str(m_date), active_v, gap, f"Gap: {gap_type}", gap * rate))
                    conn.commit(); st.rerun()

            cat = st.selectbox("Mission Type", ["Business / Work", "Medical / VA", "Charity", "Personal"])
            if st.button("🏁 ARCHIVE MISSION LOG"):
                dist = e_odo - s_odo
                rate = 0.725 if "Business" in cat else (0.22 if "Medical" in cat else 0.0)
                savings = dist * rate
                conn.execute("INSERT INTO trips (date, vehicle, miles, type, savings, start_odo, end_odo) VALUES (?,?,?,?,?,?,?)",
                             (str(m_date), active_v, dist, cat, savings, s_odo, e_odo))
                conn.commit()
                st.success(f"✔️ SECURED: You just earned ${savings:.2f} in tax deductions.")
                st.balloons()
        else: st.info("Use Sidebar to add a vehicle.")

    with t2:
        st.subheader("🎖️ IDT Deployment Details")
        mode = st.radio("Logistics Mode", ["POV (Self-Drive)", "Commercial Air", "Rental Fleet"], horizontal=True)
        c1, c2 = st.columns(2)
        with c1:
            idt_date = st.date_input("Orders Start", datetime.date.today())
            gas = st.number_input("Gas/Fuel ($)", min_value=0.0)
            tolls = st.number_input("Tolls/Parking ($)", min_value=0.0)
            lodging = st.number_input("Unreimbursed Hotel ($)", min_value=0.0)
        with c2:
            reimb = st.number_input("Gov Reimbursement ($)", value=0.0)
            transit = st.number_input("Uber/Rideshare ($)", min_value=0.0)
            laundry = st.number_input("Laundry/Incidental ($)", min_value=0.0)
            
            if mode == "POV (Self-Drive)":
                mi = st.number_input("Total Trip Miles", min_value=0.0)
                total = (mi * 0.725) + gas + tolls + lodging + transit + laundry
            elif mode == "Commercial Air":
                f_cost = st.number_input("Flight Cost ($)", min_value=0.0)
                apt_mi = st.number_input("Miles to/from Airport", min_value=0.0)
                total = f_cost + (apt_mi * 0.725) + gas + tolls + lodging + transit + laundry
            else:
                total = st.number_input("Rental Base Cost ($)", min_value=0.0) + gas + tolls + lodging + transit + laundry

        net = max(0.0, total - reimb)
        st.metric("NET IDT DEDUCTION", f"${net:.2f}")
        if st.button("🎖️ SAVE IDT RECORD"):
            conn.execute("INSERT INTO trips (date, vehicle, miles, type, fuel, tolls, lodging, transit, laundry, reimb, savings) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (str(idt_date), "IDT", 0, "Military IDT", gas, tolls, lodging, transit, laundry, reimb, net))
            conn.commit(); st.success(f"✔️ ARCHIVED: Added ${net:.2f} to your total deductions.")

    with t3:
        df_view = pd.read_sql("SELECT date, type, miles, fuel, tolls, lodging, transit as Uber_Taxi, laundry, reimb, savings as 'Deduction' FROM trips", conn)
        if not df_view.empty:
            st.metric("TOTAL 2026 DEDUCTIONS", f"${df_view['Deduction'].sum():,.2f}")
            st.dataframe(df_view, use_container_width=True)
            if st.button("🛠️ GO TO DOWNLOAD PAGE"): navigate('download')

# --- 6. EXPORT SCREEN (THE NAVIGATION TRAP FIX) ---
else:
    # 1. THE RED RETURN BUTTON - ALWAYS AT THE TOP
    st.markdown('<div class="return-btn">', unsafe_allow_html=True)
    if st.button("🔙 RETURN TO DASHBOARD"):
        navigate('main')
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    st.subheader("📩 Official Report Ready")
    st.info("Step 1: Hit Download below. \nStep 2: Save to your phone. \nStep 3: Click the RED BUTTON ABOVE to return.")
    
    df_export = pd.read_sql("SELECT * FROM trips", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False)
    
    st.download_button(label="💾 DOWNLOAD EXCEL REPORT", data=output.getvalue(), 
                       file_name=f"MilPro_Report_{datetime.date.today()}.xlsx")
