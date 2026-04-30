import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. DATABASE SETUP ---
# Incremented version to ensure fresh schema sync
conn = sqlite3.connect('milpro_tactical_v14.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date_start TEXT, date_end TEXT, vehicle TEXT, 
              start_odo REAL, end_odo REAL, dist REAL, type TEXT, details TEXT, savings REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

# IRS 2026 RATES
RATES = {"Business": 0.725, "Medical": 0.22, "Charity": 0.14, "Personal": 0.0}

# --- 2. THEME & UI ---
# The page_icon 🦅 often becomes the "App Icon" when saved to a phone home screen
st.set_page_config(page_title="Mil-Pro Command", layout="wide", page_icon="🦅")

st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        background-image: linear-gradient(rgba(14, 17, 23, 0.9), rgba(14, 17, 23, 0.9)), 
            url('https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg');
        background-attachment: fixed; background-size: cover; color: #ffffff;
    }
    section[data-testid="stSidebar"] { background-color: #1a1c24 !important; }
    h1, h2, h3, p, label { color: #ffffff !important; font-weight: bold !important; }
    [data-testid="stMetric"] { background-color: #1f2937; padding: 15px; border-radius: 10px; border: 1px solid #3b82f6; }
    [data-testid="stMetricValue"] { color: #3b82f6 !important; }
    
    .stButton>button { background-color: #1d4ed8 !important; color: white !important; font-weight: bold; width: 100%; }
    .return-btn > button { background-color: #B22234 !important; border: 2px solid #ffffff !important; } 
    </style>
    <div style="text-align: center; padding-bottom: 20px;">
        <h1 style="font-size: 2.5rem; margin-bottom: 0;">🦅 MIL-PRO COMMAND</h1>
        <p style="letter-spacing: 2px; color: #3b82f6;">RELIABLE TACTICAL LOGGING</p>
    </div>
    """, unsafe_allow_html=True)

# --- 3. NAVIGATION & APP STATE ---
if 'page' not in st.session_state:
    st.session_state.page = 'main'

def navigate(page_name):
    st.session_state.page = page_name

# --- 4. SIDEBAR: STABLE FLEET MANAGEMENT ---
with st.sidebar:
    st.header("🚘 Fleet Status")
    # Immediate fetch to ensure UI is in sync with DB
    garage_df = pd.read_sql("SELECT * FROM garage", conn)
    
    if not garage_df.empty:
        active_v = st.selectbox("ACTIVE VEHICLE", garage_df['name'].tolist(), key="fleet_select")
        if st.button("🗑️ Decommission Vehicle"):
            c.execute("DELETE FROM garage WHERE name=?", (active_v,))
            conn.commit()
            st.rerun() # Forces instant UI update
    else:
        st.warning("FLEET EMPTY")
        active_v = None

    with st.expander("➕ Register Vehicle"):
        nv_name = st.text_input("Vehicle Name", key="new_v_name")
        nv_mpg = st.number_input("MPG", min_value=1.0, value=20.0, key="new_v_mpg")
        if st.button("Confirm Registry"):
            if nv_name:
                try:
                    c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (nv_name, nv_mpg))
                    conn.commit()
                    st.rerun() # Refresh immediately to show in selectbox
                except: st.error("Database conflict. Try a new name.")

    st.divider()
    if st.checkbox("Maintenance Mode"):
        if st.button("⚠️ SYSTEM WIPE"):
            c.execute("DELETE FROM trips"); c.execute("DELETE FROM garage"); conn.commit()
            st.rerun()

# --- 5. MAIN DASHBOARD ---
if st.session_state.page == 'main':
    tab1, tab2, tab3 = st.tabs(["🚀 Mission Log", "🎖️ IDT Tactical", "📊 Executive Report"])

    with tab1:
        if active_v:
            # GAP DETECTION LOGIC
            last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{active_v}' ORDER BY id DESC LIMIT 1", conn)
            last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
            
            st.subheader(f"Unit: {active_v}")
            c1, c2, c3 = st.columns(3)
            with c1:
                m_date = st.date_input("Date", datetime.date.today())
            with c2:
                s_odo = st.number_input("Start Odometer", value=last_val)
            with c3:
                e_odo = st.number_input("End Odometer", value=s_odo + 1.0)
            
            # Show Gap Alert if current start > previous end
            if s_odo > last_val and last_val > 0:
                gap = s_odo - last_val
                st.warning(f"🚨 MILEAGE GAP DETECTED: {gap} miles unaccounted for.")
                if st.button(f"Log {gap} miles as Personal Gap"):
                    c.execute("INSERT INTO trips (date_start, date_end, vehicle, dist, type, savings) VALUES (?,?,?,?,?,?)",
                              (m_date, m_date, active_v, gap, "Personal Gap", 0.0))
                    conn.commit()
                    st.rerun()

            cat = st.selectbox("Category", ["Business", "Medical", "Charity", "Personal"])
            if st.button("🏁 Secure Mission Log"):
                dist = e_odo - s_odo
                val = dist * RATES.get(cat, 0.0)
                c.execute("INSERT INTO trips (date_start, date_end, vehicle, start_odo, end_odo, dist, type, savings) VALUES (?,?,?,?,?,?,?,?)",
                          (m_date, m_date, active_v, s_odo, e_odo, dist, cat, val))
                conn.commit()
                st.success(f"Archived. Tax Impact: +${val:.2f}")
        else:
            st.info("Register a vehicle in the sidebar to begin.")

    with tab2:
        st.subheader("🎖️ IDT Deployment")
        mode = st.radio("Method", ["POV", "Flight", "Rental"], horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            idt_s = st.date_input("Orders Start", datetime.date.today())
            idt_e = st.date_input("Orders Through", datetime.date.today())
            gas = st.number_input("Gas ($)", min_value=0.0)
            parking = st.number_input("Airport Fees ($)", min_value=0.0) if mode == "Flight" else 0.0
        with col2:
            reimb = st.number_input("Gov Reimbursement ($)", value=750.0)
            if mode == "POV":
                mi = st.number_input("Total Miles", min_value=0.0)
                total = (mi * 0.725) + gas
            elif mode == "Flight":
                f_c = st.number_input("Flight $", min_value=0.0)
                a_m = st.number_input("Airport Miles", min_value=0.0)
                total = f_c + (a_m * 0.725) + gas + parking
            else:
                total = st.number_input("Rental $", min_value=0.0) + gas
        
        net = max(0.0, total - reimb)
        st.metric("NET DEDUCTION", f"${net:.2f}")
        if st.button("🎖️ Archive IDT"):
            c.execute("INSERT INTO trips (date_start, date_end, vehicle, dist, type, details, savings) VALUES (?,?,?,?,?,?,?)",
                      (idt_s, idt_e, "IDT-TACTICAL", 0, "Military IDT", f"Mode: {mode}", net))
            conn.commit(); st.success("IDT Saved.")

    with tab3:
        df = pd.read_sql("SELECT * FROM trips", conn)
        if not df.empty:
            st.metric("TOTAL 2026 SAVINGS", f"${df['savings'].sum():,.2f}")
            st.dataframe(df, use_container_width=True)
            st.button("🛠️ Prepare Final Export", on_click=navigate, args=['download'])

# --- 6. EXPORT SCREEN ---
else:
    st.markdown('<div class="return-btn">', unsafe_allow_html=True)
    st.button("🔙 RETURN TO COMMAND DASHBOARD", on_click=navigate, args=['main'])
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    st.subheader("📩 Tactical Export Ready")
    
    df_export = pd.read_sql("SELECT * FROM trips", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Tax_Report')
    
    st.download_button(label="💾 Download Official Spreadsheet", data=output.getvalue(), 
                       file_name=f"MilPro_Report_{datetime.date.today()}.xlsx", mime="application/vnd.ms-excel")
