import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- 1. STABLE DATABASE SETUP ---
# Changing the name to 'milpro_fresh_start.db' forces the app to ignore old errors
conn = sqlite3.connect('milpro_fresh_start.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY, date TEXT, vehicle TEXT, start_odo REAL, end_odo REAL, 
              dist REAL, type TEXT, mode TEXT, fuel_cost REAL, travel_cost REAL, 
              per_diem REAL, savings REAL, excess_deduction REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

# --- 2. 2026 TAX RATES (IRS Standard) ---
RATES = {"Business": 0.725, "Medical": 0.22, "Charity": 0.14, "Personal": 0.0}

def save_trip(date, vehicle, start, end, t_type, mode, fuel, travel, per_diem, savings, excess):
    dist = float(end - start) if end > start else 0.0
    c.execute("""INSERT INTO trips (date, vehicle, start_odo, end_odo, dist, type, mode, fuel_cost, travel_cost, per_diem, savings, excess_deduction) 
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
              (str(date), str(vehicle), float(start), float(end), dist, str(t_type), str(mode), float(fuel), float(travel), float(per_diem), float(savings), float(excess)))
    conn.commit()

# --- 3. APP INTERFACE ---
st.set_page_config(page_title="Mil-Pro Tax-Max", layout="wide", page_icon="💰")
st.title("💰 Mil-Pro: Tax & IDT Logistics")

# --- SIDEBAR: GARAGE ---
with st.sidebar:
    st.header("🚘 Garage")
    garage_df = pd.read_sql("SELECT * FROM garage", conn)
    
    if not garage_df.empty:
        selected_v = st.selectbox("Active Vehicle", garage_df['name'].tolist())
        current_mpg = float(garage_df[garage_df['name'] == selected_v]['mpg'].values[0])
        if st.button("🗑️ Delete Vehicle"):
            c.execute("DELETE FROM garage WHERE name=?", (selected_v,))
            conn.commit()
            st.rerun()
    else:
        st.warning("Step 1: Add a vehicle below!")
        selected_v = None

    with st.expander("➕ Add New Vehicle"):
        nv_name = st.text_input("Vehicle Name (e.g., Ford F-150)")
        nv_mpg = st.number_input("Vehicle MPG", min_value=1.0, value=18.0)
        if st.button("Save to Garage"):
            try:
                c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (nv_name, nv_mpg))
                conn.commit()
                st.rerun()
            except: st.error("Error: Make sure the name is unique.")

# --- MAIN TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🚗 Standard Log", "🎖️ IDT Tactical", "📅 History", "💎 Tax Report"])

# --- TAB 1: STANDARD LOG ---
with tab1:
    if selected_v:
        # Fetch last odometer safely
        last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1", conn)
        last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
        
        st.subheader(f"Logging for: {selected_v}")
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Date", datetime.date.today(), key="std_date")
            cat = st.selectbox("Deduction Category", ["Business", "Medical", "Charity", "Personal"])
            s_odo = st.number_input("Start Odometer", value=last_val)
            
            # --- GAP FILLER ---
            if s_odo > last_val and last_val > 0:
                gap = s_odo - last_val
                st.warning(f"⚠️ {gap} mile gap detected since last trip!")
                gap_cat = st.selectbox("Classify the gap:", ["Personal", "Business", "Medical", "Charity"])
                if st.button(f"Log Gap as {gap_cat}"):
                    g_savings = gap * RATES.get(gap_cat, 0.0)
                    save_trip(date, selected_v, last_val, s_odo, gap_cat, "Gap Fill", 0, 0, 0, g_savings, 0)
                    st.success(f"Logged {gap} miles as {gap_cat}!")
                    st.rerun()
        
        with col2:
            e_odo = st.number_input("End Odometer", value=s_odo + 1.0)
            gas_p = st.number_input("Gas Price/Gal", value=3.50)
            
        dist = e_odo - s_odo
        total_savings = dist * RATES.get(cat, 0.0)
        
        st.info(f"**Trip Impact:** {dist:.1f} miles | **Tax Deduction:** ${total_savings:.2f}")
        
        if st.button("🚀 Finalize & Save Trip", use_container_width=True):
            fuel_cost = (dist / current_mpg) * gas_p
            save_trip(date, selected_v, s_odo, e_odo, cat, "Ground", fuel_cost, 0, 0, total_savings, 0)
            st.success("Trip successfully saved to log!")
            st.rerun()
    else:
        st.info("👈 Open the sidebar to add a vehicle first!")

# --- TAB 2: IDT TACTICAL ---
with tab2:
    if selected_v:
        st.subheader("Military IDT Deployment & Tax Strategy")
        mode = st.radio("Primary Travel Mode", ["POV (Personal Car)", "Rental", "Flight"], horizontal=True)
        
        c1, c2 = st.columns(2)
        with c1:
            idt_d = st.date_input("Duty Date", datetime.date.today(), key="idt_date")
            duty_days = st.number_input("Days on Duty (incl. travel days)", min_value=1, value=2)
            per_diem_rate = st.number_input("GSA Per Diem M&IE ($)", value=59.0)
            
            if mode == "Flight":
                f_cost = st.number_input("Flight Ticket Price ($)", value=0.0)
                p_cost = st.number_input("Airport Parking ($)", value=0.0)
                r_dest = st.number_input("Dest. Rental/Uber ($)", value=0.0)
                dist_idt = st.number_input("Miles to/from Airport (POV)", value=15.0)
            else:
                dist_ow = st.number_input("One-Way Distance to Unit", value=50.0)
                is_rt = st.checkbox("Round Trip?", value=True)
                dist_idt = dist_ow * 2 if is_rt else dist_ow
                r_cost = st.number_input("Rental/Tolls (Out of Pocket) ($)", value=0.0) if mode == "Rental" else 0.0

        with c2:
            st.write("### The Reimbursement Gap")
            reimbursement = st.number_input("Amount Military Paid/Will Pay You ($)", value=0.0)
            gas_idt = st.number_input("Local Gas Price ($)", value=3.50)

        # IDT CALCULATIONS
        pov_tax_val = dist_idt * RATES["Business"]
        total_per_diem = duty_days * per_diem_rate
        out_of_pocket = (f_cost + p_cost + r_dest) if mode == "Flight" else r_cost
        
        total_value = pov_tax_val + total_per_diem + out_of_pocket
        excess_deduct = max(0.0, total_value - reimbursement)

        st.divider()
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Trip IRS Value", f"${total_value:.2f}")
        col_m2.metric("Unreimbursed Tax Deduction", f"${excess_deduct:.2f}")

        if st.button("🎖️ Log Tactical Military Record", use_container_width=True):
            fuel_idt = (dist_idt / current_mpg) * gas_idt
            save_trip(idt_d, selected_v, 0, dist_idt, "IDT Military", mode, fuel_idt, out_of_pocket, total_per_diem, reimbursement, excess_deduct)
            st.success("Military Record Saved!")
    else:
        st.info("Select a vehicle in the sidebar to start IDT logging.")

# --- TAB 3: HISTORY ---
with tab3:
    st.subheader("Master Tactical History")
    df_hist = pd.read_sql("SELECT * FROM trips ORDER BY id DESC", conn)
    st.dataframe(df_hist, use_container_width=True)

# --- TAB 4: TAX REPORT ---
with tab4:
    df_tax = pd.read_sql("SELECT * FROM trips", conn)
    if not df_tax.empty:
        st.header("💎 2026 Executive Tax Summary")
        met1, met2, met3 = st.columns(3)
        met1.metric("Mileage Deduction", f"${df_tax['savings'].sum():,.2f}")
        met2.metric("IDT Unreimbursed", f"${df_tax['excess_deduction'].sum():,.2f}")
        met3.metric("Total Claimable", f"${df_tax['savings'].sum() + df_tax['excess_deduction'].sum():,.2f}")
        
        st.divider()
        st.subheader("Deduction Types")
        st.bar_chart(df_tax.groupby('type')['savings'].sum())
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_tax.to_excel(writer, sheet_name='Tax_Report_2026', index=False)
        st.download_button("📩 Download Professional Report", data=buf.getvalue(), file_name="MilPro_Final_Report.xlsx", use_container_width=True)
    else:
        st.info("Log your first trip to generate your tax summary.")
