import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. STABLE DATABASE SETUP ---
conn = sqlite3.connect('milpro_v5_final.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY, date TEXT, vehicle TEXT, start_odo REAL, end_odo REAL, 
              dist REAL, type TEXT, fuel_spent REAL, savings REAL, actual_expense REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY, name TEXT UNIQUE, mpg REAL, is_low_mpg INTEGER)''')
conn.commit()

# IRS 2026 RATES
RATES = {"Business": 0.725, "Medical": 0.22, "Charity": 0.14, "Personal": 0.0}

# --- 2. APP INTERFACE & MILITARY THEME ---
st.set_page_config(page_title="Mil-Pro Tactical Tracker", layout="wide", page_icon="🇺🇸")

# Military Header & Flag Background Styling
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stApp {
        border-top: 12px solid #B22234; /* Old Glory Red */
    }
    h1 {
        color: #3C3B6E; /* Old Glory Blue */
        text-shadow: 1px 1px 2px #ccc;
    }
    .stButton>button {
        background-color: #3C3B6E !important;
        color: white !important;
        font-weight: bold;
    }
    </style>
    <div style="text-align: center; padding: 10px;">
        <h1>🇺🇸 MIL-PRO TACTICAL TAX TRACKER 🇺🇸</h1>
        <p><i>Integrity First • Service Before Self • Excellence in All We Do</i></p>
    </div>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR: THE GARAGE ---
with st.sidebar:
    st.header("🚘 Tactical Garage")
    garage_df = pd.read_sql("SELECT * FROM garage", conn)
    
    if not garage_df.empty:
        selected_v = st.selectbox("Active Vehicle", garage_df['name'].tolist())
        v_info = garage_df[garage_df['name'] == selected_v].iloc[0]
        if v_info['is_low_mpg']:
            st.warning("⚠️ Low MPG: Tracking actual expenses recommended.")
        
        if st.button("🗑️ Retire Vehicle"):
            c.execute("DELETE FROM garage WHERE name=?", (selected_v,))
            conn.commit()
            st.rerun()
    else:
        st.info("Step 1: Register your vehicle.")
        selected_v = None

    with st.expander("➕ Register New Vehicle"):
        nv_name = st.text_input("Vehicle Name (e.g. Ford F-150)")
        nv_mpg = st.number_input("Average MPG", min_value=1.0, value=15.0)
        if st.button("Save to Garage"):
            low_mpg_flag = 1 if nv_mpg < 18 else 0
            c.execute("INSERT INTO garage (name, mpg, is_low_mpg) VALUES (?,?,?)", (nv_name, nv_mpg, low_mpg_flag))
            conn.commit()
            st.rerun()

# --- 4. MAIN NAVIGATION TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Mission Log (GPS)", "🎖️ IDT Tactical", "📊 Executive Report"])

# --- TAB 1: MISSION LOG & GAP DETECTION ---
with tab1:
    if selected_v:
        # Check for Odometer Gaps
        last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
        last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
        
        st.subheader(f"Unit: {selected_v}")
        col1, col2 = st.columns(2)
        with col1:
            s_odo = st.number_input("Start Odometer (GPS Sync)", value=last_val)
            # Gap Logic
            if s_odo > last_val and last_val > 0:
                gap = s_odo - last_val
                st.error(f"🚨 GAP DETECTED: {gap} miles missing!")
                gap_cat = st.selectbox("Classify Gap Miles", ["Personal", "Business", "Medical", "Charity"])
                if st.button("Recover Gap Miles"):
                    g_savings = gap * RATES.get(gap_cat, 0.0)
                    c.execute("INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, savings) VALUES (?,?,?,?,?,?,?)",
                              (datetime.date.today(), selected_v, last_val, s_odo, gap, gap_cat, g_savings))
                    conn.commit()
                    st.success("Miles recovered!")
                    st.rerun()
        
        with col2:
            e_odo = st.number_input("End Odometer", value=s_odo + 1.0)
            cat = st.selectbox("Mission Type", ["Business", "Medical", "Charity", "Personal"])

        st.divider()
        st.subheader("⛽ Refuel Intel")
        refuel = st.checkbox("Did you refuel during this sortie?")
        f_cost = 0.0
        if refuel:
            f_cost = st.number_input("Total Fuel Cost ($)", value=0.0)

        if st.button("🏁 End Mission & Save Log", use_container_width=True):
            dist = e_odo - s_odo
            savings = dist * RATES.get(cat, 0.0)
            # Accountant logic: Fuel + flat wear rate for 'Actual Expense' comparison
            actual = f_cost + (dist * 0.22) 
            
            c.execute("""INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, fuel_spent, savings, actual_expense) 
                         VALUES (?,?,?,?,?,?,?,?,?)""",
                      (datetime.date.today(), selected_v, s_odo, e_odo, dist, cat, f_cost, savings, actual))
            conn.commit()
            st.balloons()
            st.success(f"Log Secure. You saved ${savings:.2f} in tax deductions!")
            st.rerun()
    else:
        st.info("👈 Open the sidebar to register your vehicle first.")

# --- TAB 2: IDT TACTICAL ---
with tab2:
    st.subheader("Military IDT & Duty Logistics")
    st.markdown("Use this for Inactive Duty Training (Drill) or orders where you aren't fully reimbursed.")
    
    i1, i2 = st.columns(2)
    with i1:
        idt_date = st.date_input("Duty Date", datetime.date.today())
        idt_mode = st.radio("Transport Mode", ["POV (Personal)", "Rental", "Flight"])
        dist_ow = st.number_input("One-Way Distance", value=50.0)
    with i2:
        reimb = st.number_input("Reimbursement Received (DTS/GSA) ($)", value=0.0)
        fuel_idt = st.number_input("Fuel/Parking/Tolls Out-of-Pocket ($)", value=0.0)

    # Tactical Math
    total_idt_dist = dist_ow * 2
    standard_val = total_idt_dist * 0.725
    total_cost = fuel_idt + standard_val
    claimable = max(0.0, total_cost - reimb)

    st.metric("Unreimbursed Claimable Deduction", f"${claimable:.2f}")
    
    if st.button("🎖️ Save IDT Tactical Record", use_container_width=True):
        c.execute("INSERT INTO trips (date, vehicle, dist, type, savings) VALUES (?,?,?,?,?)",
                  (idt_date, "IDT-Military", total_idt_dist, "IDT", claimable))
        conn.commit()
        st.success("Tactical Record Logged.")

# --- TAB 3: EXECUTIVE REPORT ---
with tab3:
    st.header("📊 Accountant-Ready Report")
    df = pd.read_sql("SELECT * FROM trips", conn)
    
    if not df.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Tax Savings", f"${df['savings'].sum():,.2f}")
        m2.metric("Total Fuel Spent", f"${df['fuel_spent'].sum():,.2f}")
        m3.metric("Mission Miles", f"{df['dist'].sum():,.1f}")

        st.divider()
        st.dataframe(df, use_container_width=True)

        # Excel Export Logic
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Tax_Log_2026', index=False)
        
        st.download_button("📩 Download Final Spreadsheet", data=buf.getvalue(), 
                           file_name=f"MilPro_Tax_Report_{datetime.date.today()}.xlsx", 
                           use_container_width=True)
