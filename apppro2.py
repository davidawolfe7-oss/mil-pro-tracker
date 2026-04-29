import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- DATABASE SETUP ---
conn = sqlite3.connect('milpro_tax_pro.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY, date TEXT, vehicle TEXT, start_odo REAL, end_odo REAL, 
              dist REAL, type TEXT, mode TEXT, fuel_cost REAL, travel_cost REAL, 
              per_diem REAL, savings REAL, excess_deduction REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

# --- 2026 TAX RATES ---
RATES = {
    "Business/POV": 0.725,
    "Medical": 0.22,
    "Charity": 0.14,
    "Personal": 0.0
}

def save_trip(date, vehicle, start, end, t_type, mode, fuel, travel, per_diem, savings, excess):
    dist = end - start if end > start else 0
    c.execute("""INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, mode, fuel_cost, travel_cost, per_diem, savings, excess_deduction) 
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (date, vehicle, start, end, dist, t_type, mode, fuel, travel, per_diem, savings, excess))
    conn.commit()

st.set_page_config(page_title="Mil-Pro Tax-Max", layout="wide", page_icon="💰")
st.title("💰 Mil-Pro: Tax Deduction & IDT Engine")

# --- SIDEBAR: GARAGE ---
with st.sidebar:
    st.header("🚘 Vehicle & Tax Profile")
    garage_df = pd.read_sql("SELECT * FROM garage", conn)
    if not garage_df.empty:
        selected_v = st.selectbox("Active Vehicle", garage_df['name'].tolist())
        current_mpg = garage_df[garage_df['name'] == selected_v]['mpg'].values[0]
    else:
        st.warning("Add a vehicle below")
        selected_v = None

    with st.expander("➕ Add/Manage Garage"):
        nv_name = st.text_input("Vehicle Name")
        nv_mpg = st.number_input("MPG", min_value=1.0, value=20.0)
        if st.button("Save Vehicle"):
            try:
                c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (nv_name, nv_mpg))
                conn.commit()
                st.rerun()
            except: st.error("Exists!")

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🚗 Daily Log", "🎖️ IDT Tax Strategy", "📅 History", "💎 Tax Report"])

# --- TAB 1: DAILY LOG (Standard) ---
with tab1:
    if selected_v:
        last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
        last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
        
        st.subheader("Standard Deduction Entry")
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Date", datetime.date.today())
            cat = st.selectbox("Deduction Category", ["Business", "Medical", "Charity", "Personal"])
            s_odo = st.number_input("Start Odometer", value=last_val)
        with col2:
            e_odo = st.number_input("End Odometer", value=s_odo + 1.0)
            gas_p = st.number_input("Gas Price/Gal", value=3.50)
            
        dist = e_odo - s_odo
        tax_rate = RATES.get("Business/POV") if cat == "Business" else RATES.get(cat)
        total_deduction = dist * tax_rate
        
        # Gap Logic
        if s_odo > last_val and last_val != 0:
            gap = s_odo - last_val
            st.warning(f"⚠️ {gap} mile gap! Classify this for your taxes:")
            g_cat = st.selectbox("Gap Category", ["Personal", "Business", "Medical", "Charity"])
            if st.button(f"Log Gap as {g_cat}"):
                save_trip(date, selected_v, last_val, s_odo, g_cat, "Gap Fill", 0, 0, 0, gap * RATES.get(g_cat, 0), 0)
                st.rerun()

        st.info(f"**Potential Tax Deduction:** ${total_deduction:.2f}")
        if st.button("🚀 Save Trip to Tax Log", use_container_width=True):
            save_trip(date, selected_v, s_odo, e_odo, cat, "Ground", (dist/current_mpg)*gas_p, 0, 0, total_deduction, 0)
            st.success("Logged!")
            st.rerun()

# --- TAB 2: IDT MILITARY (The Bread & Butter) ---
with tab2:
    if selected_v:
        st.subheader("IDT Deployment & Travel Deductions")
        mode = st.radio("Travel Mode", ["Personal Car (POV)", "Rental Car", "Flight"], horizontal=True)
        
        c1, c2 = st.columns(2)
        with c1:
            idt_date = st.date_input("Duty Date", datetime.date.today(), key="idt_d")
            days_on_duty = st.number_input("Total Days on Duty/Travel", min_value=1, value=2)
            per_diem_rate = st.number_input("Standard Per Diem Rate ($)", value=59.0) # Standard M&IE
            
            if mode == "Flight":
                t_cost = st.number_input("Flight Cost ($)", value=0.0)
                p_cost = st.number_input("Airport Parking ($)", value=0.0)
                r_cost = st.number_input("Rental/Uber at Destination ($)", value=0.0)
            else:
                dist_ow = st.number_input("One-Way Distance", value=50.0)
                is_rt = st.checkbox("Round Trip", value=True)
                r_cost = st.number_input("Rental/Tolls (Out of Pocket) ($)", value=0.0) if mode == "Rental Car" else 0.0

        with c2:
            st.write("### Reimbursement vs Deduction")
            expected_reimburse = st.number_input("Total Expected from Military Claim ($)", value=0.0)
            gas_idt = st.number_input("Gas Price", value=3.50, key="idt_g")
        
        # MATH ENGINE
        total_m = (dist_ow * 2 if is_rt else dist_ow) if mode != "Flight" else 0
        pov_tax_val = total_m * RATES["Business/POV"]
        total_per_diem = days_on_duty * per_diem_rate
        
        # Total "Actual Value" of the trip
        out_of_pocket = (t_cost if mode == "Flight" else 0) + r_cost + (p_cost if mode == "Flight" else 0)
        total_trip_value = pov_tax_val + total_per_diem + out_of_pocket
        
        # The Secret Sauce: Excess Deduction
        # Anything the military doesn't pay back is potentially tax deductible
        excess = total_trip_value - expected_reimburse
        if excess < 0: excess = 0

        st.divider()
        col_a, col_b = st.columns(2)
        col_a.metric("IRS Value of Trip", f"${total_trip_value:.2f}")
        col_b.metric("Potential Tax Deduction", f"${excess:.2f}", delta="Unreimbursed")
        
        if excess > 0:
            st.success(f"💡 Strategy: Since your military claim is only ${expected_reimburse}, you can potentially deduct the remaining ${excess:.2f} on your taxes.")

        if st.button("🎖️ Finalize IDT Tax Record", use_container_width=True):
            save_trip(idt_date, selected_v, 0, total_m, "IDT Military", mode, (total_m/current_mpg)*gas_idt, out_of_pocket, total_per_diem, expected_reimburse, excess)
            st.success("Tactical Tax Record Saved!")

# --- TAB 3: HISTORY ---
with tab3:
    history = pd.read_sql("SELECT * FROM trips ORDER BY id DESC", conn)
    st.dataframe(history, use_container_width=True)

# --- TAB 4: TAX REPORT ---
with tab4:
    df = pd.read_sql("SELECT * FROM trips", conn)
    if not df.empty:
        st.header("💎 2026 Tax Preparation Summary")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Mileage Deduction", f"${df['savings'].sum():,.2f}")
        m2.metric("Unreimbursed IDT Deductions", f"${df['excess_deduction'].sum():,.2f}")
        m3.metric("Total Tax Impact", f"${df['savings'].sum() + df['excess_deduction'].sum():,.2f}")
        
        st.divider()
        st.subheader("Deduction Breakdown")
        chart_df = df.groupby('type')[['savings', 'excess_deduction']].sum()
        st.bar_chart(chart_df)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Tax_Log_2026', index=False)
        st.download_button("📩 Download Professional Tax Report", data=buffer.getvalue(), file_name=f"Tax_Report_{datetime.date.today()}.xlsx", use_container_width=True)
