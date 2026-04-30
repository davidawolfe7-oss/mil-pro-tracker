import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. DATABASE ---
def get_db_connection():
    conn = sqlite3.connect('milpro_tactical_v19.db', check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

conn = get_db_connection()
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, vehicle TEXT, 
              miles REAL, type TEXT, fuel REAL, tolls REAL, lodging REAL, 
              transit REAL, laundry REAL, reimb REAL, savings REAL, notes TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

# --- 2. THEME & FLAG ---
st.set_page_config(page_title="Mil-Pro Command", layout="wide", page_icon="🦅")

st.markdown("""
    <style>
    .stApp {
        background-image: linear-gradient(rgba(14, 17, 23, 0.8), rgba(14, 17, 23, 0.8)), 
            url('https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg');
        background-attachment: fixed; background-size: cover; color: #ffffff;
    }
    [data-testid="stMetric"] { background-color: #1f2937; border: 1px solid #3b82f6; border-radius: 8px; }
    .stButton>button { background-color: #1d4ed8 !important; color: white !important; font-weight: bold; width: 100%; height: 3.5em; }
    .return-btn > button { background-color: #B22234 !important; border: 2px solid white !important; height: 5em !important; font-size: 1.2rem !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. NAVIGATION ---
if 'page' not in st.session_state: st.session_state.page = 'main'
def navigate(page_name): st.session_state.page = page_name

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("🚘 Fleet Status")
    garage_df = pd.read_sql("SELECT * FROM garage ORDER BY name ASC", conn)
    active_v = st.selectbox("ACTIVE VEHICLE", garage_df['name'].tolist()) if not garage_df.empty else None
    
    with st.expander("➕ Register Unit"):
        n = st.text_input("Name")
        m = st.number_input("MPG", value=20.0)
        if st.button("Add"):
            try:
                c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (n, m)); conn.commit(); st.rerun()
            except: st.info("Unit exists.")

# --- 5. MAIN DASHBOARD ---
if st.session_state.page == 'main':
    t1, t2, t3 = st.tabs(["🚀 Mission Log", "🎖️ IDT Logistics", "📊 Report"])

    with t1:
        if active_v:
            # --- GAP DETECTION & FLEXIBLE CATEGORY ---
            last_q = pd.read_sql(f"SELECT end_odo FROM (SELECT id, end_odo FROM trips WHERE vehicle='{active_v}' AND end_odo IS NOT NULL ORDER BY id DESC LIMIT 1)", conn)
            last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
            
            st.subheader(f"Log Sortie: {active_v}")
            c1, c2, c3 = st.columns(3)
            with c1: m_date = st.date_input("Date", datetime.date.today())
            with c2: s_odo = st.number_input("Start Odo", value=last_val)
            with c3: e_odo = st.number_input("End Odo", value=s_odo + 1.0)
            
            if s_odo > last_val and last_val > 0:
                gap_miles = s_odo - last_val
                st.warning(f"🚨 {gap_miles} MILE GAP DETECTED")
                gap_cat = st.selectbox("Assign Gap To:", ["Personal", "Business / Work", "Medical / VA", "Charity"], key="gap_cat")
                if st.button(f"Log {gap_miles} Mile Gap as {gap_cat}"):
                    rate = 0.725 if "Business" in gap_cat else (0.22 if "Medical" in gap_cat else 0.0)
                    c.execute("INSERT INTO trips (date, vehicle, miles, type, savings) VALUES (?,?,?,?,?)",
                              (str(m_date), active_v, gap_miles, f"Gap: {gap_cat}", gap_miles * rate))
                    conn.commit(); st.rerun()

            # --- DEDUCTION NOTIFICATION ---
            cat = st.selectbox("Mission Category", ["Business / Work", "Medical / VA", "Charity", "Personal"])
            if st.button("🏁 SECURE MISSION LOG"):
                dist = e_odo - s_odo
                rate = 0.725 if "Business" in cat else (0.22 if "Medical" in cat else 0.0)
                savings = dist * rate
                c.execute("INSERT INTO trips (date, vehicle, miles, type, savings, start_odo, end_odo) VALUES (?,?,?,?,?,?,?)",
                          (str(m_date), active_v, dist, cat, savings, s_odo, e_odo))
                conn.commit()
                st.success(f"✔️ LOGGED: You saved ${savings:.2f} in tax deductions!")
                st.balloons()
        else: st.info("Register a vehicle in the sidebar.")

    with t2:
        st.subheader("🎖️ Deployment Logistics")
        mode = st.radio("Primary Method", ["Personal Vehicle", "Commercial Flight", "Rental Car"], horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            idt_date = st.date_input("Orders Start", datetime.date.today())
            gas = st.number_input("Fuel/Gas ($)", min_value=0.0)
            tolls = st.number_input("Tolls & Bridge Fees ($)", min_value=0.0)
            lodging = st.number_input("Hotel/Lodging ($)", min_value=0.0)
        with col2:
            reimb = st.number_input("Gov Reimbursement ($)", value=0.0)
            transit = st.number_input("Rideshare / Taxi ($)", min_value=0.0)
            laundry = st.number_input("Laundry Service ($)", min_value=0.0)
            
            if mode == "Personal Vehicle":
                mi = st.number_input("Round Trip Miles", min_value=0.0)
                total = (mi * 0.725) + gas + tolls + lodging + transit + laundry
            elif mode == "Commercial Flight":
                f_cost = st.number_input("Flight Price ($)", min_value=0.0)
                apt_mi = st.number_input("Airport POV Miles", min_value=0.0)
                total = f_cost + (apt_mi * 0.725) + gas + tolls + lodging + transit + laundry
            else:
                total = st.number_input("Rental Base ($)", min_value=0.0) + gas + tolls + lodging + transit + laundry

        net = max(0.0, total - reimb)
        st.metric("IDT TAX IMPACT", f"${net:.2f}")
        if st.button("🎖️ ARCHIVE IDT RECORD"):
            c.execute("INSERT INTO trips (date, vehicle, miles, type, fuel, tolls, lodging, transit, laundry, reimb, savings) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (str(idt_date), "IDT", 0, "Military IDT", gas, tolls, lodging, transit, laundry, reimb, net))
            conn.commit(); st.success(f"IDT LOGGED: You saved ${net:.2f} in tax deductions!")

    with t3:
        df_view = pd.read_sql("SELECT date, type, miles, fuel, tolls, lodging, transit, laundry, reimb, savings as 'Deduction' FROM trips", conn)
        if not df_view.empty:
            st.metric("TOTAL 2026 DEDUCTIONS", f"${df_view['Deduction'].sum():,.2f}")
            st.dataframe(df_view, use_container_width=True)
            if st.button("🛠️ OPEN EXPORT CONTROL"): navigate('download')

# --- 6. EXPORT SCREEN (THE NAVIGATION FIX) ---
else:
    # RETURN BUTTON AT THE VERY TOP - Visible before/after file interaction
    st.markdown('<div class="return-btn">', unsafe_allow_html=True)
    if st.button("🔙 EXIT & RETURN TO DASHBOARD"):
        navigate('main')
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    st.subheader("📩 Official Spreadsheet Ready")
    st.info("After you click download, your phone may open 'Numbers' or a save menu. When finished, use the RED BUTTON ABOVE to go back.")
    
    df_export = pd.read_sql("SELECT * FROM trips", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False)
    
    # This button stays here. The user hits this, phone pops up its menu, user handles file, then clicks the red button.
    st.download_button(label="💾 DOWNLOAD MIL-PRO REPORT", data=output.getvalue(), 
                       file_name=f"MilPro_Final_{datetime.date.today()}.xlsx")
