import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. DATABASE SETUP ---
conn = sqlite3.connect('milpro_v8_night_ops.db', check_same_thread=False)
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
    /* Main Background with American Flag Watermark */
    .stApp {
        background-color: #0e1117;
        background-image: linear-gradient(rgba(14, 17, 23, 0.85), rgba(14, 17, 23, 0.85)), 
            url('https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg');
        background-attachment: fixed;
        background-size: cover;
        color: #ffffff;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #1a1c24 !important;
    }

    /* Header & Text Visibility */
    h1, h2, h3, p, label { color: #ffffff !important; }
    
    /* Professional Metric Cards */
    [data-testid="stMetric"] {
        background-color: #1f2937;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #374151;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.5);
    }
    [data-testid="stMetricValue"] { color: #3b82f6 !important; font-weight: bold !important; }
    [data-testid="stMetricDelta"] { color: #10b981 !important; }

    /* Button Styling - Tactical Blue */
    .stButton>button {
        background-color: #1d4ed8 !important;
        color: white !important;
        border: none;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #2563eb !important;
        transform: scale(1.02);
    }

    /* Dataframe Visibility */
    .stDataFrame { background-color: #1f2937; border-radius: 10px; }
    </style>
    
    <div style="text-align: center; padding-bottom: 20px;">
        <h1 style="font-size: 3rem; margin-bottom: 0;">🦅 MIL-PRO COMMAND</h1>
        <p style="letter-spacing: 2px; color: #9ca3af;">TACTICAL TAX INTELLIGENCE</p>
    </div>
    """, unsafe_allow_html=True)

# --- 3. LOGIC & NAVIGATION ---
if 'page' not in st.session_state:
    st.session_state.page = 'main'

if st.session_state.page == 'main':
    # --- GARAGE (SIDEBAR) ---
    with st.sidebar:
        st.header("🚘 Active Fleet")
        garage_df = pd.read_sql("SELECT * FROM garage", conn)
        selected_v = st.selectbox("Current Vehicle", garage_df['name'].tolist()) if not garage_df.empty else None
        
        if st.button("🗑️ Decommission Vehicle") and selected_v:
            c.execute("DELETE FROM garage WHERE name=?", (selected_v,))
            conn.commit()
            st.rerun()

        st.divider()
        with st.expander("➕ Register Vehicle"):
            nv_name = st.text_input("Name")
            nv_mpg = st.number_input("MPG", min_value=1.0, value=20.0)
            if st.button("Save to Fleet"):
                try:
                    c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (nv_name, nv_mpg))
                    conn.commit()
                    st.rerun()
                except: st.error("Name already exists.")

    # --- MAIN CONTENT ---
    tab1, tab2, tab3 = st.tabs(["🚀 Mission Log", "🎖️ IDT Tactical", "📊 Executive Report"])

    with tab1:
        if selected_v:
            last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
            last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
            
            st.subheader(f"Current Sortie: {selected_v}")
            c1, c2 = st.columns(2)
            with c1:
                s_odo = st.number_input("Start Odometer", value=last_val)
                if s_odo > last_val and last_val > 0:
                    st.error(f"🚨 GAP DETECTED: {s_odo - last_val} miles missing.")
            with c2:
                e_odo = st.number_input("End Odometer", value=s_odo + 10.0)
                cat = st.selectbox("Deduction Category", ["Business", "Medical", "Charity", "Personal"])

            if st.button("🏁 Secure Mission Log", use_container_width=True):
                dist = e_odo - s_odo
                val = dist * RATES.get(cat, 0.0)
                c.execute("INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, savings) VALUES (?,?,?,?,?,?,?)",
                          (datetime.date.today(), selected_v, s_odo, e_odo, dist, cat, val))
                conn.commit()
                st.toast(f"Log Secure. Tax Impact: +${val:.2f}", icon="💰")
                st.balloons()
        else:
            st.info("👈 Register a vehicle in the sidebar to start logging.")

    with tab2:
        st.subheader("🎖️ IDT Tactical Deployment")
        mode = st.radio("Logistics Mode", ["POV (Self Drive)", "Flight / Commercial", "Rental Unit"], horizontal=True)
        
        col1, col2 = st.columns(2)
        with col1:
            idt_date = st.date_input("Orders Date", datetime.date.today())
            gas = st.number_input("Gas Expense ($)", min_value=0.0)
            tolls = st.number_input("Tolls ($)", min_value=0.0)
            parking = st.number_input("Parking / Airport Fees ($)", min_value=0.0)
        
        with col2:
            reimb = st.number_input("Government Reimbursement (DTS) ($)", min_value=0.0)
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
        st.metric("NET UNREIMBURSED BENEFIT", f"${net_deduction:.2f}", delta="Tax Deduction Potential")

        if st.button("🎖️ Archive Tactical Record", use_container_width=True):
            details = f"Mode: {mode} | Costs: G:${gas} T:${tolls} P:${parking}"
            c.execute("INSERT INTO trips (date, vehicle, dist, type, details, savings) VALUES (?,?,?,?,?,?)",
                      (idt_date, "IDT-LOG", 0, "Military IDT", details, net_deduction))
            conn.commit()
            st.success("Record Saved to Command.")

    with tab3:
        st.subheader("📊 Tactical Financial Summary")
        df = pd.read_sql("SELECT date, vehicle, dist as miles, type, details, savings FROM trips", conn)
        
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            if st.button("🛠️ Generate Professional Report"):
                st.session_state.page = 'download'
                st.rerun()
        else:
            st.info("Mission history is currently empty.")

# --- 4. DOWNLOAD PAGE ---
else:
    st.subheader("📩 Professional Report Ready")
    df_export = pd.read_sql("SELECT date, vehicle, start_odo, end_odo, dist as miles, type, details, savings FROM trips", conn)
    
    # Advanced Excel Styling
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Tax_Report')
        workbook = writer.book
        worksheet = writer.sheets['Tax_Report']
        
        # Header formatting
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1d4ed8', 'font_color': 'white', 
            'border': 1, 'align': 'center'
        })
        # Money formatting
        money_fmt = workbook.add_format({'num_format': '$#,##0.00'})
        
        for col_num, value in enumerate(df_export.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 18)
        
        worksheet.set_column('H:H', 18, money_fmt) # Apply money format to Savings

    st.download_button(
        label="💾 Download Official 2026 Tax Spreadsheet",
        data=output.getvalue(),
        file_name=f"Tactical_Tax_Report_{datetime.date.today()}.xlsx",
        mime="application/vnd.ms-excel",
        use_container_width=True
    )
    
    if st.button("🔙 Return to Dashboard"):
        st.session_state.page = 'main'
        st.rerun()
