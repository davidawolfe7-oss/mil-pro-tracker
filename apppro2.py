import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. DATABASE SETUP ---
conn = sqlite3.connect('milpro_tactical_v11.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, vehicle TEXT, 
              start_odo REAL, end_odo REAL, dist REAL, type TEXT, details TEXT, savings REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

# IRS 2026 RATES
RATES = {"Business": 0.725, "Medical": 0.22, "Charity": 0.14, "Personal": 0.0}

# --- 2. THEME & UI ---
st.set_page_config(page_title="Mil-Pro Night Ops", layout="wide", page_icon="🇺🇸")

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
    .main-btn > button { background-color: #10b981 !important; } /* Success Green for Return Button */
    </style>
    <div style="text-align: center; padding-bottom: 20px;">
        <h1 style="font-size: 2.5rem; margin-bottom: 0;">🦅 MIL-PRO COMMAND</h1>
        <p style="letter-spacing: 2px; color: #3b82f6;">MISSION LOGISTICS & TAX INTELLIGENCE</p>
    </div>
    """, unsafe_allow_html=True)

# --- 3. NAVIGATION LOGIC ---
if 'page' not in st.session_state:
    st.session_state.page = 'main'

def go_to_main():
    st.session_state.page = 'main'

def go_to_download():
    st.session_state.page = 'download'

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("🚘 Fleet Status")
    garage_df = pd.read_sql("SELECT * FROM garage", conn)
    
    if not garage_df.empty:
        active_v = st.selectbox("SELECT ACTIVE VEHICLE", garage_df['name'].tolist())
        st.success(f"ONLINE: {active_v}")
        if st.button("🗑️ Decommission Vehicle"):
            c.execute("DELETE FROM garage WHERE name=?", (active_v,))
            conn.commit()
            st.rerun()
    else:
        st.warning("FLEET EMPTY")
        active_v = None

    with st.expander("➕ Register Vehicle"):
        nv_name = st.text_input("Name")
        nv_mpg = st.number_input("MPG", min_value=1.0, value=20.0)
        if st.button("Add to Fleet"):
            try:
                c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (nv_name, nv_mpg))
                conn.commit()
                st.rerun()
            except: st.error("Name locked in database.")

    st.divider()
    if st.checkbox("Show System Tools"):
        if st.button("⚠️ FACTORY RESET (Wipe All)"):
            c.execute("DELETE FROM trips"); c.execute("DELETE FROM garage"); conn.commit()
            st.rerun()

# --- 5. MAIN DASHBOARD ---
if st.session_state.page == 'main':
    tab1, tab2, tab3 = st.tabs(["🚀 Mission Log", "🎖️ IDT Tactical", "📊 Executive Report"])

    with tab1:
        if active_v:
            last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{active_v}' ORDER BY id DESC LIMIT 1", conn)
            last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
            st.subheader(f"Log Mission: {active_v}")
            c1, c2 = st.columns(2)
            with c1:
                s_odo = st.number_input("Start Odometer", value=last_val)
            with c2:
                e_odo = st.number_input("End Odometer", value=s_odo + 5.0)
                cat = st.selectbox("Category", ["Business", "Medical", "Charity", "Personal"])

            if st.button("🏁 Finalize Mission Log"):
                dist = e_odo - s_odo
                val = dist * RATES.get(cat, 0.0)
                c.execute("INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, savings) VALUES (?,?,?,?,?,?,?)",
                          (datetime.date.today(), active_v, s_odo, e_odo, dist, cat, val))
                conn.commit()
                st.success(f"Log Secured. Tax Credit: ${val:.2f}")
                st.balloons()
        else:
            st.info("Register a vehicle in the sidebar to begin.")

    with tab2:
        st.subheader("🎖️ IDT Deployment Logistics")
        mode = st.radio("Travel Mode", ["POV", "Flight", "Rental"], horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            idt_date = st.date_input("Orders Date", datetime.date.today())
            gas = st.number_input("Gas ($)", min_value=0.0)
            parking = st.number_input("Parking/Airport Fees ($)", min_value=0.0)
        with col2:
            reimb = st.number_input("DTS Reimbursement ($)", min_value=0.0)
            if mode == "POV":
                miles = st.number_input("Round-Trip Miles", min_value=0.0)
                total_cost = (miles * 0.725) + gas + parking
            elif mode == "Flight":
                f_cost = st.number_input("Flight Cost ($)", min_value=0.0)
                apt_mi = st.number_input("Miles to Airport", min_value=0.0)
                total_cost = f_cost + (apt_mi * 0.725) + parking
            else:
                total_cost = st.number_input("Rental Total ($)", min_value=0.0) + gas + parking

        net = max(0.0, total_cost - reimb)
        st.metric("IDT TAX BENEFIT", f"${net:.2f}")
        if st.button("🎖️ Archive IDT Record"):
            c.execute("INSERT INTO trips (date, vehicle, dist, type, details, savings) VALUES (?,?,?,?,?,?)",
                      (idt_date, "IDT-MIL", 0, "Military IDT", f"Mode: {mode}", net))
            conn.commit()
            st.success("IDT Saved.")

    with tab3:
        st.subheader("📊 Tactical Report")
        df = pd.read_sql("SELECT * FROM trips", conn)
        if not df.empty:
            st.metric("TOTAL DEDUCTIONS", f"${df['savings'].sum():,.2f}")
            st.dataframe(df, use_container_width=True)
            # This triggers the "Download Page"
            st.button("🛠️ Prepare Final Export", on_click=go_to_download)
        else:
            st.info("No data found.")

# --- 6. EXPORT SCREEN (THE FIX) ---
else:
    st.subheader("📩 Tactical Export Ready")
    st.markdown("Your 2026 Tax Spreadsheet has been compiled. Download it below and then return to the dashboard.")
    
    df_export = pd.read_sql("SELECT * FROM trips", conn)
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
        label="💾 Download Official Spreadsheet",
        data=output.getvalue(),
        file_name=f"Tactical_Tax_Report_{datetime.date.today()}.xlsx",
        mime="application/vnd.ms-excel"
    )
    
    st.divider()
    
    # THE RE-ENTRY POINT
    st.markdown('<div class="main-btn">', unsafe_allow_html=True)
    if st.button("🔙 RETURN TO COMMAND DASHBOARD", on_click=go_to_main, use_container_width=True):
        pass # The on_click handler does the work
    st.markdown('</div>', unsafe_allow_html=True)
