import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. DATABASE SETUP ---
conn = sqlite3.connect('milpro_v7_tactical.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, vehicle TEXT, 
              dist REAL, type TEXT, details TEXT, savings REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

# IRS 2026 RATES
RATES = {"Business": 0.725, "Medical": 0.22, "Charity": 0.14, "Personal": 0.0}

# --- 2. APP INTERFACE & HIGH-CONTRAST THEME ---
st.set_page_config(page_title="Mil-Pro Tactical", layout="wide", page_icon="🇺🇸")

st.markdown("""
    <style>
    .stApp { border-top: 15px solid #B22234; background-color: #f4f7f6; }
    h1, h2, h3 { color: #002868 !important; font-family: 'Arial Black', sans-serif; }
    
    /* Metric Card Fix - High Visibility */
    [data-testid="stMetricValue"] { color: #002868 !important; font-size: 2rem !important; font-weight: bold !important; }
    [data-testid="stMetricDelta"] { color: #B22234 !important; font-weight: bold !important; }
    [data-testid="stMetric"] { 
        background-color: #ffffff; 
        padding: 15px; 
        border-radius: 10px; 
        border: 2px solid #002868;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    
    .stButton>button { 
        background-color: #002868 !important; 
        color: white !important; 
        font-weight: bold; 
        border-radius: 5px;
        height: 3em;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #e0e0e0;
        border-radius: 5px 5px 0px 0px;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #002868 !important; color: white !important; }
    </style>
    <div style="text-align: center;">
        <h1>🇺🇸 MIL-PRO TACTICAL COMMAND 🇺🇸</h1>
        <p style="color: #333;"><i>Strategic Tax Deduction & Logistics Log</i></p>
    </div>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR: GARAGE ---
with st.sidebar:
    st.header("🚘 Fleet Management")
    garage_df = pd.read_sql("SELECT * FROM garage", conn)
    selected_v = st.selectbox("Active Vehicle", garage_df['name'].tolist()) if not garage_df.empty else None
    
    if st.button("🗑️ Remove Selected Vehicle") and selected_v:
        c.execute("DELETE FROM garage WHERE name=?", (selected_v,))
        conn.commit()
        st.rerun()

    st.divider()
    with st.expander("➕ Register New Vehicle"):
        nv_name = st.text_input("Vehicle Name")
        nv_mpg = st.number_input("MPG", min_value=1.0, value=20.0)
        if st.button("Confirm Registration"):
            try:
                c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (nv_name, nv_mpg))
                conn.commit()
                st.success("Vehicle Added to Fleet")
                st.rerun()
            except: st.error("Duplicate Name Detected.")

# --- 4. NAVIGATION ---
if 'page' not in st.session_state:
    st.session_state.page = 'main'

if st.session_state.page == 'main':
    tab1, tab2, tab3 = st.tabs(["🚀 Mission Log", "🎖️ IDT Tactical", "📊 Executive Report"])

    # --- TAB 1: MISSION LOG ---
    with tab1:
        if selected_v:
            last_q = pd.read_sql(f"SELECT end_odo FROM (SELECT end_odo, id FROM trips WHERE vehicle='{selected_v}' AND end_odo IS NOT NULL ORDER BY id DESC LIMIT 1)", conn)
            last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
            
            st.subheader(f"Unit: {selected_v}")
            c1, c2 = st.columns(2)
            with c1:
                s_odo = st.number_input("Start Odometer", value=last_val)
                if s_odo > last_val and last_val > 0:
                    gap = s_odo - last_val
                    st.error(f"🚨 GAP DETECTED: {gap} Miles Missing")
                    if st.button("Log Gap as Personal (Cleanup)"):
                        c.execute("INSERT INTO trips (date, vehicle, dist, type, savings) VALUES (?,?,?,?,?)",
                                  (datetime.date.today(), selected_v, gap, "Personal Gap", 0))
                        conn.commit()
                        st.rerun()
            with c2:
                e_odo = st.number_input("End Odometer", value=s_odo + 5.0)
                cat = st.selectbox("Mission Type", ["Business", "Medical", "Charity", "Personal"])

            if st.button("🏁 Finalize Mission Log", use_container_width=True):
                dist = e_odo - s_odo
                savings = dist * RATES.get(cat, 0.0)
                c.execute("INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, savings) VALUES (?,?,?,?,?,?,?)",
                          (datetime.date.today(), selected_v, s_odo, e_odo, dist, cat, savings))
                conn.commit()
                st.success(f"✅ MISSION SECURE: Estimated Tax Benefit: ${savings:.2f}")
                st.balloons()
        else:
            st.warning("Register a vehicle in the sidebar to begin.")

    # --- TAB 2: IDT TACTICAL ---
    with tab2:
        st.subheader("🎖️ Inactive Duty Training (IDT) Logistics")
        mode = st.radio("Primary Travel Method", ["POV (Driving Personal Car)", "Flight / Commercial", "Rental Only"], horizontal=True)
        
        col1, col2 = st.columns(2)
        with col1:
            idt_date = st.date_input("Duty Date", datetime.date.today())
            gas = st.number_input("Gas Expense ($)", min_value=0.0)
            tolls = st.number_input("Tolls ($)", min_value=0.0)
            parking = st.number_input("Parking Fees ($)", min_value=0.0)
        
        with col2:
            reimb = st.number_input("DTS / Government Reimbursement ($)", min_value=0.0)
            if mode == "POV (Driving Personal Car)":
                miles = st.number_input("Total Round-Trip Miles", min_value=0.0)
                total_cost = (miles * 0.725) + gas + tolls + parking
            elif mode == "Flight / Commercial":
                f_cost = st.number_input("Flight Ticket Cost ($)", min_value=0.0)
                apt_miles = st.number_input("Miles to/from Airport (Home)", min_value=0.0)
                dest_rent = st.number_input("Destination Rental/Uber ($)", min_value=0.0)
                total_cost = f_cost + (apt_miles * 0.725) + dest_rent + tolls + parking
            else:
                r_cost = st.number_input("Total Rental Cost ($)", min_value=0.0)
                total_cost = r_cost + gas + tolls + parking

        net_deduction = max(0.0, total_cost - reimb)
        
        st.divider()
        st.metric("IDT UNREIMBURSED BENEFIT", f"${net_deduction:.2f}", help="Total cost of travel minus what the military paid you.")

        if st.button("🎖️ Archive IDT Tactical Record", use_container_width=True):
            details = f"Mode: {mode} | Gas: {gas} | Tolls: {tolls} | Parking: {parking}"
            c.execute("INSERT INTO trips (date, vehicle, dist, type, details, savings) VALUES (?,?,?,?,?,?)",
                      (idt_date, "IDT-MIL", 0, "Military IDT", details, net_deduction))
            conn.commit()
            st.success("Tactical record stored.")

    # --- TAB 3: EXECUTIVE REPORT ---
    with tab3:
        st.subheader("📊 Executive Financial Summary")
        df = pd.read_sql("SELECT date, vehicle, dist as miles, type, details, savings as tax_value FROM trips", conn)
        
        if not df.empty:
            m1, m2 = st.columns(2)
            m1.metric("TOTAL TAX DEDUCTIONS", f"${df['tax_value'].sum():,.2f}")
            m2.metric("TOTAL MISSION MILES", f"{df['miles'].sum():,.1f}")
            
            st.dataframe(df, use_container_width=True)
            
            if st.button("🛠️ Prepare Final Spreadsheet"):
                st.session_state.page = 'download'
                st.rerun()
        else:
            st.info("No data recorded for this period.")

# --- 5. DOWNLOAD PAGE ---
else:
    st.subheader("📩 Tactical Export Ready")
    df_export = pd.read_sql("SELECT * FROM trips", conn)
    
    # Professional Excel Styling
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='2026_Tax_Log')
        workbook = writer.book
        worksheet = writer.sheets['2026_Tax_Log']
        
        # Add formatting
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#002868', 'font_color': 'white', 'border': 1})
        for col_num, value in enumerate(df_export.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 15) # Adjust width
            
    st.download_button(
        label="💾 Download Official Spreadsheet",
        data=output.getvalue(),
        file_name=f"MilPro_Tax_Log_{datetime.date.today()}.xlsx",
        mime="application/vnd.ms-excel"
    )
    
    if st.button("🔙 Return to Command Dashboard"):
        st.session_state.page = 'main'
        st.rerun()
