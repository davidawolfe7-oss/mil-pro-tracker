import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. HARDENED DATABASE SETUP ---
# I've moved to a 'WAL' (Write-Ahead Logging) mode which prevents those "Locked" or "Double Input" errors
def get_db_connection():
    conn = sqlite3.connect('milpro_tactical_v15.db', check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;') # Prevents the 'database is locked' glitch
    return conn

conn = get_db_connection()
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date_start TEXT, date_end TEXT, vehicle TEXT, 
              start_odo REAL, end_odo REAL, dist REAL, type TEXT, details TEXT, savings REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

# IRS 2026 RATES
RATES = {"Business": 0.725, "Medical": 0.22, "Charity": 0.14, "Personal": 0.0}

# --- 2. UI & THEME ---
st.set_page_config(page_title="Mil-Pro Command", layout="wide", page_icon="🦅")

st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        background-image: linear-gradient(rgba(14, 17, 23, 0.9), rgba(14, 17, 23, 0.9)), 
            url('https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg');
        background-attachment: fixed; background-size: cover; color: #ffffff;
    }
    section[data-testid="stSidebar"] { background-color: #1a1c24 !important; min-width: 350px !important; }
    h1, h2, h3, p, label { color: #ffffff !important; font-weight: bold !important; }
    [data-testid="stMetric"] { background-color: #1f2937; padding: 15px; border-radius: 10px; border: 1px solid #3b82f6; }
    .stButton>button { background-color: #1d4ed8 !important; color: white !important; font-weight: bold; width: 100%; height: 3em; }
    .return-btn > button { background-color: #B22234 !important; border: 2px solid #ffffff !important; } 
    </style>
    <div style="text-align: center; padding-bottom: 20px;">
        <h1 style="font-size: 2.5rem; margin-bottom: 0;">🦅 MIL-PRO COMMAND</h1>
        <p style="letter-spacing: 2px; color: #3b82f6;">STRATEGIC FLEET OPERATIONS</p>
    </div>
    """, unsafe_allow_html=True)

# --- 3. PERSISTENT NAVIGATION ---
if 'page' not in st.session_state:
    st.session_state.page = 'main'

def navigate(page_name):
    st.session_state.page = page_name

# --- 4. SIDEBAR: THE STABLE FLEET CONTROLLER ---
with st.sidebar:
    st.header("🚘 Fleet Status")
    
    # 1. Fetch current garage
    garage_df = pd.read_sql("SELECT * FROM garage ORDER BY name ASC", conn)
    
    # 2. Display selection or empty state
    if not garage_df.empty:
        v_list = garage_df['name'].tolist()
        active_v = st.selectbox("ACTIVE VEHICLE", v_list, key="v_selector")
        
        # Pull MPG for the active one
        mpg_val = garage_df[garage_df['name'] == active_v]['mpg'].values[0]
        st.success(f"STATUS: {active_v} ONLINE ({mpg_val} MPG)")
        
        if st.button("🗑️ DECOMMISSION VEHICLE"):
            c.execute("DELETE FROM garage WHERE name=?", (active_v,))
            conn.commit()
            st.rerun()
    else:
        st.warning("⚠️ FLEET EMPTY: Register a vehicle below.")
        active_v = None

    st.divider()
    
    # 3. Dedicated Registration Form (Prevents the "Double Entry" Glitch)
    st.subheader("➕ Register New Unit")
    with st.form("vehicle_form", clear_on_submit=True):
        new_name = st.text_input("Unit Name (e.g., RAM 1500)")
        new_mpg = st.number_input("Unit MPG", min_value=1.0, value=20.0)
        submitted = st.form_submit_state = st.form_submit_button("LOCK INTO FLEET")
        
        if submitted:
            if new_name:
                try:
                    c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (new_name, new_mpg))
                    conn.commit()
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That name is already in the database. Use 'Maintenance Mode' to wipe if needed.")
            else:
                st.error("Name is required.")

    st.divider()
    if st.checkbox("Maintenance Mode"):
        if st.button("🚨 FACTORY DATA RESET"):
            c.execute("DELETE FROM trips"); c.execute("DELETE FROM garage"); conn.commit()
            st.rerun()

# --- 5. MAIN DASHBOARD ---
if st.session_state.page == 'main':
    tab1, tab2, tab3 = st.tabs(["🚀 Mission Log", "🎖️ IDT Tactical", "📊 Executive Report"])

    with tab1:
        if active_v:
            # GAP DETECTION
            last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{active_v}' ORDER BY id DESC LIMIT 1", conn)
            last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
            
            st.subheader(f"Current Sortie: {active_v}")
            c1, c2, c3 = st.columns(3)
            with c1:
                m_date = st.date_input("Date", datetime.date.today())
            with c2:
                s_odo = st.number_input("Start Odometer", value=last_val)
            with c3:
                e_odo = st.number_input("End Odometer", value=s_odo + 1.0)
            
            if s_odo > last_val and last_val > 0:
                gap = s_odo - last_val
                st.warning(f"🚨 GAP: {gap} Miles Missing.")
                if st.button(f"Log {gap} Miles as Personal Gap"):
                    c.execute("INSERT INTO trips (date_start, date_end, vehicle, dist, type, savings) VALUES (?,?,?,?,?,?)",
                              (m_date, m_date, active_v, gap, "Personal Gap", 0.0))
                    conn.commit(); st.rerun()

            cat = st.selectbox("Category", ["Business", "Medical", "Charity", "Personal"])
            if st.button("🏁 SECURE LOG"):
                dist = e_odo - s_odo
                val = dist * RATES.get(cat, 0.0)
                c.execute("INSERT INTO trips (date_start, date_end, vehicle, start_odo, end_odo, dist, type, savings) VALUES (?,?,?,?,?,?,?,?)",
                          (m_date, m_date, active_v, s_odo, e_odo, dist, cat, val))
                conn.commit(); st.success("Log Saved."); st.balloons()
        else:
            st.info("👈 Register your first vehicle in the sidebar to unlock the Mission Log.")

    with tab2:
        st.subheader("🎖️ IDT Tactical (Multi-Day Orders)")
        mode = st.radio("Logistics", ["POV", "Flight", "Rental"], horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            idt_s = st.date_input("Orders Start", datetime.date.today())
            idt_e = st.date_input("Orders Through", datetime.date.today())
            gas = st.number_input("Total Gas ($)", min_value=0.0)
            park = st.number_input("Airport Fees ($)", min_value=0.0) if mode == "Flight" else 0.0
        with col2:
            reimb = st.number_input("Total Reimbursement ($)", value=750.0)
            if mode == "POV":
                mi = st.number_input("POV Round-Trip Miles", min_value=0.0)
                total = (mi * 0.725) + gas
            elif mode == "Flight":
                f_c = st.number_input("Flight Ticket ($)", min_value=0.0)
                a_m = st.number_input("Airport Drive Miles", min_value=0.0)
                total = f_c + (a_m * 0.725) + gas + park
            else:
                total = st.number_input("Rental Base ($)", min_value=0.0) + gas
        
        net = max(0.0, total - reimb)
        st.metric("UNREIMBURSED DEDUCTION", f"${net:.2f}")
        if st.button("🎖️ ARCHIVE IDT DATA"):
            c.execute("INSERT INTO trips (date_start, date_end, vehicle, dist, type, details, savings) VALUES (?,?,?,?,?,?,?)",
                      (idt_s, idt_e, "IDT-TACTICAL", 0, "Military IDT", f"Mode: {mode}", net))
            conn.commit(); st.success("Tactical Data Stored.")

    with tab3:
        df = pd.read_sql("SELECT * FROM trips", conn)
        if not df.empty:
            st.metric("TOTAL ACCUMULATED SAVINGS", f"${df['savings'].sum():,.2f}")
            st.dataframe(df, use_container_width=True)
            st.button("🛠️ PREPARE FINAL EXPORT", on_click=navigate, args=['download'])

else:
    # RETURN BUTTON
    st.markdown('<div class="return-btn">', unsafe_allow_html=True)
    st.button("🔙 RETURN TO COMMAND DASHBOARD", on_click=navigate, args=['main'])
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    df_export = pd.read_sql("SELECT * FROM trips", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Tax_Log')
    
    st.download_button(label="💾 DOWNLOAD OFFICIAL 2026 LOG", data=output.getvalue(), 
                       file_name=f"MilPro_Tax_Report_{datetime.date.today()}.xlsx", mime="application/vnd.ms-excel")
        
