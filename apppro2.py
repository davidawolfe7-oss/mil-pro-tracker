import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. HARDENED DATABASE ---
def get_db_connection():
    conn = sqlite3.connect('milpro_tactical_v17.db', check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

conn = get_db_connection()
c = conn.cursor()
# Schema updated to include specific IDT line items for the accountant
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, vehicle TEXT, 
              dist REAL, type TEXT, fuel REAL, tolls REAL, lodging REAL, 
              transit REAL, laundry REAL, reimb REAL, savings REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

# --- 2. TACTICAL UI (FLAG RESTORED) ---
st.set_page_config(page_title="Mil-Pro Command", layout="wide", page_icon="🦅")

st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        background-image: linear-gradient(rgba(14, 17, 23, 0.85), rgba(14, 17, 23, 0.85)), 
            url('https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg');
        background-attachment: fixed; background-size: cover; color: #ffffff;
    }
    [data-testid="stMetric"] { background-color: #1f2937; border: 1px solid #3b82f6; border-radius: 10px; }
    .stButton>button { background-color: #1d4ed8 !important; color: white !important; font-weight: bold; width: 100%; height: 3.5em; }
    .return-btn > button { background-color: #B22234 !important; border: 2px solid white !important; margin-top: 20px; }
    </style>
    <div style="text-align: center; padding-bottom: 20px;">
        <h1 style="font-size: 2.5rem; margin-bottom: 0;">🦅 MIL-PRO COMMAND</h1>
        <p style="letter-spacing: 2px; color: #3b82f6;">RELIABLE TACTICAL LOGGING</p>
    </div>
    """, unsafe_allow_html=True)

# --- 3. NAVIGATION ---
if 'page' not in st.session_state: st.session_state.page = 'main'
def navigate(page_name): st.session_state.page = page_name

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("🚘 Fleet Status")
    garage_df = pd.read_sql("SELECT * FROM garage ORDER BY name ASC", conn)
    active_v = st.selectbox("ACTIVE VEHICLE", garage_df['name'].tolist()) if not garage_df.empty else None
    
    with st.expander("➕ Register Vehicle"):
        n = st.text_input("Unit Name")
        m = st.number_input("Unit MPG", value=20.0)
        if st.button("Add to Fleet"):
            c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (n, m)); conn.commit(); st.rerun()

# --- 5. MAIN DASHBOARD ---
if st.session_state.page == 'main':
    t1, t2, t3 = st.tabs(["🚀 Mission Log", "🎖️ IDT Tactical", "📊 Executive Report"])

    with t1:
        if active_v:
            st.subheader(f"Log Sortie: {active_v}")
            # Simplified Mission Log (Odo still there but report will hide it)
            c1, c2, c3 = st.columns(3)
            with c1: m_date = st.date_input("Date", datetime.date.today())
            with c2: s_odo = st.number_input("Start Odo")
            with c3: e_odo = st.number_input("End Odo")
            
            cat = st.selectbox("Duty Category", ["Business / Work", "Medical / VA", "Charity / Volunteer", "Personal / Gap"])
            if st.button("🏁 Secure Mission Log"):
                dist = e_odo - s_odo
                rate = 0.725 if "Business" in cat else (0.22 if "Medical" in cat else 0.0)
                savings = dist * rate
                c.execute("INSERT INTO trips (date, vehicle, dist, type, savings) VALUES (?,?,?,?,?)",
                          (m_date, active_v, dist, cat, savings))
                conn.commit(); st.success("Stored."); st.balloons()
        else: st.info("Register a vehicle in the sidebar.")

    with t2:
        st.subheader("🎖️ IDT Deployment Logistics")
        mode = st.radio("Primary Travel Method", ["Personal Vehicle", "Commercial Flight", "Rental Car"], horizontal=True)
        
        col1, col2 = st.columns(2)
        with col1:
            idt_date = st.date_input("Start of Orders", datetime.date.today())
            gas = st.number_input("Fuel / Gas Costs ($)", min_value=0.0)
            tolls = st.number_input("Tolls & Bridge Fees ($)", min_value=0.0)
            lodging = st.number_input("Unreimbursed Hotel / Lodging ($)", min_value=0.0)
        with col2:
            reimb = st.number_input("Gov Reimbursement Received ($)", value=750.0)
            transit = st.number_input("Rideshare / Uber / Taxi ($)", min_value=0.0)
            laundry = st.number_input("Laundry / Incidental ($)", min_value=0.0)
            
            if mode == "Personal Vehicle":
                mi = st.number_input("Round Trip Miles", min_value=0.0)
                total_exp = (mi * 0.725) + gas + tolls + lodging + transit + laundry
            elif mode == "Commercial Flight":
                f_cost = st.number_input("Flight Ticket Price ($)", min_value=0.0)
                apt_mi = st.number_input("Miles to Airport (Home)", min_value=0.0)
                total_exp = f_cost + (apt_mi * 0.725) + gas + tolls + lodging + transit + laundry
            else:
                total_exp = st.number_input("Rental Base Price ($)", min_value=0.0) + gas + tolls + lodging + transit + laundry

        net = max(0.0, total_exp - reimb)
        st.metric("NET TAX DEDUCTION", f"${net:.2f}")
        if st.button("🎖️ Archive Tactical Record"):
            c.execute("INSERT INTO trips (date, vehicle, dist, type, fuel, tolls, lodging, transit, laundry, reimb, savings) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (idt_date, "IDT-TACTICAL", 0, "Military IDT", gas, tolls, lodging, transit, laundry, reimb, net))
            conn.commit(); st.success("IDT Saved.")

    with t3:
        # Accountant-Focused View
        df = pd.read_sql("SELECT date, type, dist as miles, fuel, tolls, lodging, transit, laundry, reimb, savings as 'Net Deduction' FROM trips", conn)
        if not df.empty:
            st.metric("TOTAL 2026 DEDUCTIONS", f"${df['Net Deduction'].sum():,.2f}")
            st.dataframe(df, use_container_width=True)
            st.button("🛠️ Prepare Final Export", on_click=navigate, args=['download'])

# --- 6. EXPORT SCREEN ---
elif st.session_state.page == 'download':
    st.subheader("📩 Tactical Export Ready")
    
    df_export = pd.read_sql("SELECT * FROM trips", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False)
    
    # Download Button
    st.download_button(label="💾 DOWNLOAD OFFICIAL REPORT", data=output.getvalue(), 
                       file_name=f"MilPro_Tax_Report_{datetime.date.today()}.xlsx")
    
    st.divider()
    # THIS is the button that takes you back to main AFTER you download
    st.markdown("### 🏁 Mission Complete?")
    st.write("Once you have finished your download, hit the button below to return to the dashboard.")
    if st.button("🔙 RETURN TO COMMAND DASHBOARD", on_click=navigate, args=['main']):
        pass

# --- 7. THE "NUMBERS" TRAP FIX ---
# This is a hidden page that only exists to break the mobile app out of the file preview
elif st.session_state.page == 'post_download':
    st.markdown('<div class="return-btn">', unsafe_allow_html=True)
    st.button("🔙 BACK TO MAIN DASHBOARD", on_click=navigate, args=['main'])
    st.markdown('</div>', unsafe_allow_html=True)
