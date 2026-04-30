import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. STABLE DATABASE SETUP ---
# Incremented version to ensure a clean schema start
conn = sqlite3.connect('milpro_v6_tactical.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, vehicle TEXT, 
              start_odo REAL, end_odo REAL, dist REAL, type TEXT, 
              fuel_spent REAL, savings REAL, actual_expense REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, 
              mpg REAL, is_low_mpg INTEGER)''')
conn.commit()

# IRS 2026 RATES
RATES = {"Business": 0.725, "Medical": 0.22, "Charity": 0.14, "Personal": 0.0}

# --- 2. APP INTERFACE & MILITARY THEME ---
st.set_page_config(page_title="Mil-Pro Tactical Tracker", layout="wide", page_icon="🇺🇸")

st.markdown("""
    <style>
    .stApp { border-top: 12px solid #B22234; }
    h1 { color: #3C3B6E; text-align: center; }
    .stButton>button { background-color: #3C3B6E !important; color: white !important; width: 100%; }
    .stMetric { background-color: #f1f3f6; padding: 10px; border-radius: 10px; border-left: 5px solid #3C3B6E; }
    </style>
    <div>
        <h1>🇺🇸 MIL-PRO TACTICAL TAX TRACKER 🇺🇸</h1>
        <p style="text-align: center;"><i>Precision Tracking for Service Members</i></p>
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
            st.warning(f"⚠️ {selected_v} has low MPG. We are automatically tracking 'Actual Expenses' for a potentially higher deduction.")
        
        if st.button("🗑️ Retire Vehicle"):
            c.execute("DELETE FROM garage WHERE name=?", (selected_v,))
            conn.commit()
            st.rerun()
    else:
        st.info("No vehicles registered. Add one below.")
        selected_v = None

    st.divider()
    with st.expander("➕ Register New Vehicle"):
        nv_name = st.text_input("Name (e.g. Chevy Silverado)")
        nv_mpg = st.number_input("Average MPG", min_value=1.0, value=15.0)
        if st.button("Save to Garage"):
            if nv_name:
                try:
                    low_mpg_flag = 1 if nv_mpg < 18 else 0
                    c.execute("INSERT INTO garage (name, mpg, is_low_mpg) VALUES (?,?,?)", (nv_name, nv_mpg, low_mpg_flag))
                    conn.commit()
                    st.success(f"{nv_name} Added!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("This vehicle name already exists! Try adding a year or color (e.g. '2024 F-150').")
            else:
                st.error("Please enter a name.")

# --- 4. MAIN NAVIGATION TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Mission Log (GPS)", "🎖️ IDT Tactical", "📊 Executive Report"])

# --- TAB 1: MISSION LOG ---
with tab1:
    if selected_v:
        # Check for Odometer Gaps
        last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
        last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
        
        st.subheader(f"Unit: {selected_v}")
        c1, c2 = st.columns(2)
        with c1:
            s_odo = st.number_input("Start Odometer", value=last_val)
            # Gap Logic
            if s_odo > last_val and last_val > 0:
                gap = s_odo - last_val
                st.error(f"🚨 GAP DETECTED: {gap} miles missing!")
                gap_cat = st.selectbox("Classify Gap Miles", ["Business", "Medical", "Charity", "Personal"], key="gap_sel")
                if st.button("Reconcile Missing Miles"):
                    g_savings = gap * RATES.get(gap_cat, 0.0)
                    c.execute("INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, savings, actual_expense) VALUES (?,?,?,?,?,?,?,?)",
                              (datetime.date.today(), selected_v, last_val, s_odo, gap, gap_cat, g_savings, 0))
                    conn.commit()
                    st.success("Log Integrity Restored.")
                    st.rerun()
        
        with c2:
            e_odo = st.number_input("End Odometer", value=s_odo + 1.0)
            cat = st.selectbox("Mission Category", ["Business", "Medical", "Charity", "Personal"], key="main_cat")

        st.divider()
        st.subheader("⛽ Refuel Log")
        refuel = st.checkbox("Did you add fuel during this trip?")
        f_cost = st.number_input("Fuel Cost ($)", value=0.0) if refuel else 0.0

        if st.button("🏁 End Trip & Save", use_container_width=True):
            dist = e_odo - s_odo
            savings = dist * RATES.get(cat, 0.0)
            # Actual Expense Logic: Fuel + maintenance estimate ($0.22/mile)
            actual = f_cost + (dist * 0.22) 
            
            c.execute("""INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, fuel_spent, savings, actual_expense) 
                         VALUES (?,?,?,?,?,?,?,?,?)""",
                      (datetime.date.today(), selected_v, s_odo, e_odo, dist, cat, f_cost, savings, actual))
            conn.commit()
            st.balloons()
            st.toast(f"Saved! Deduction: ${savings:.2f}")
            st.rerun()
    else:
        st.info("Step 1: Open the sidebar and register a vehicle.")

# --- TAB 2: IDT TACTICAL ---
with tab2:
    st.subheader("Military IDT & Orders Tracker")
    st.markdown("> Use this for Drill or Travel where your DTS/GSA pay didn't cover the full cost.")
    
    col_a, col_b = st.columns(2)
    with col_a:
        idt_date = st.date_input("Date of Orders", datetime.date.today())
        idt_mode = st.radio("Mode", ["POV (Personal)", "Rental", "Flight"])
        idt_dist_ow = st.number_input("One-Way Miles", value=50.0)
    with col_b:
        idt_pay = st.number_input("Military Reimbursement Received ($)", value=0.0)
        idt_costs = st.number_input("Gas/Parking/Tolls Spent ($)", value=0.0)

    # Calculation logic
    total_idt_mi = idt_dist_ow * 2
    irs_value = total_idt_mi * 0.725
    real_out_of_pocket = idt_costs + irs_value
    net_deduction = max(0.0, real_out_of_pocket - idt_pay)

    st.metric("Unreimbursed Tax Deduction", f"${net_deduction:.2f}", delta="Net Benefit")
    
    if st.button("🎖️ Save Military Tactical Log"):
        c.execute("INSERT INTO trips (date, vehicle, dist, type, savings, fuel_spent) VALUES (?,?,?,?,?,?)",
                  (idt_date, "IDT-MIL", total_idt_mi, "IDT Military", net_deduction, idt_costs))
        conn.commit()
        st.success("Orders Logged.")

# --- TAB 3: EXECUTIVE REPORT ---
with tab3:
    st.header("📊 Final Tax Report (Accountant Ready)")
    df = pd.read_sql("SELECT date, vehicle, dist, type, fuel_spent, savings as mileage_deduction, actual_expense FROM trips", conn)
    
    if not df.empty:
        # High-level stats
        m1, m2, m3 = st.columns(3)
        m1.metric("Standard Mileage Deduction", f"${df['mileage_deduction'].sum():,.2f}")
        m2.metric("Total Fuel/Expense Log", f"${df['fuel_spent'].sum() + df['actual_expense'].sum():,.2f}")
        m3.metric("Total Mission Miles", f"{df['dist'].sum():,.1f}")

        st.divider()
        st.dataframe(df, use_container_width=True)

        # Excel Export
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='2026_Tax_Log', index=False)
        
        st.download_button("📩 Download Final Spreadsheet", data=buf.getvalue(), 
                           file_name=f"MilPro_Tax_Report_{datetime.date.today()}.xlsx", 
                           use_container_width=True)
    else:
        st.info("Log your first sortie to see the report.")
