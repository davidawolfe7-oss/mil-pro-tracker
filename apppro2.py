import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io

# --- DATABASE SETUP ---
conn = sqlite3.connect('mileage.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY, date TEXT, vehicle TEXT, start_odo REAL, end_odo REAL, type TEXT, savings REAL)''')
conn.commit()

def save_trip(date, vehicle, start, end, t_type, savings):
    c.execute("INSERT INTO trips (date, vehicle, start_odo, end_odo, type, savings) VALUES (?,?,?,?,?,?)",
              (date, vehicle, start, end, t_type, savings))
    conn.commit()

# --- APP INTERFACE ---
st.set_page_config(page_title="Mil-Pro Tracker", layout="centered")
st.title("🎖️ Mil-Pro Mileage Tracker")

# Sidebar for Vehicle Management
with st.sidebar:
    st.header("📋 Garage")
    # Simple storage for vehicle list in session state
    if 'vehicles' not in st.session_state:
        st.session_state.vehicles = ["Primary Truck"]
    
    new_v = st.text_input("Add New Vehicle")
    if st.button("Add"):
        st.session_state.vehicles.append(new_v)
    
    selected_v = st.selectbox("Current Vehicle", st.session_state.vehicles)

tab1, tab2, tab3 = st.tabs(["🚗 Log Trip", "📅 History", "📊 Export"])

# --- TAB 1: LOG TRIP ---
with tab1:
    st.header("Log New Trip")
    
    # Safe Odometer Lookup
    last_end_odo = 0.0
    try:
        query = f"SELECT end_odo FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC LIMIT 1"
        last_entry = pd.read_sql(query, conn)
        if not last_entry.empty:
            last_end_odo = float(last_entry['end_odo'].iloc[0])
    except:
        last_end_odo = 0.0

    date = st.date_input("Date", datetime.date.today())
    start_odo = st.number_input("Start Odometer", value=last_end_odo, step=0.1)
    end_odo = st.number_input("End Odometer", value=start_odo + 1.0, step=0.1)
    
    # Gap Detection
    if last_end_odo > 0 and start_odo > last_end_odo:
        gap = start_odo - last_end_odo
        st.warning(f"⚠️ Gap of {gap} miles detected!")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Log as Personal"):
                save_trip(date, selected_v, last_end_odo, start_odo, "Personal", 0.0)
                st.rerun()
        with c2:
            if st.button("Log as Business"):
                save_trip(date, selected_v, last_end_odo, start_odo, "Business (Gap)", gap * 0.67)
                st.rerun()

    if st.button("Save Current Trip"):
        miles = end_odo - start_odo
        if miles > 0:
            savings = miles * 0.67
            save_trip(date, selected_v, start_odo, end_odo, "Business", savings)
            st.success(f"Saved! ${savings:.2f} earned.")
            st.rerun()
        else:
            st.error("End Odometer must be higher than Start.")

# --- TAB 2: HISTORY ---
with tab2:
    st.header("Trip Logs")
    history_df = pd.read_sql(f"SELECT * FROM trips WHERE vehicle='{selected_v}' ORDER BY id DESC", conn)
    if not history_df.empty:
        st.dataframe(history_df)
    else:
        st.info("No trips logged for this vehicle yet.")

# --- TAB 3: EXPORT ---
with tab3:
    st.header("Executive Export")
    export_df = pd.read_sql("SELECT * FROM trips", conn)
    
    if not export_df.empty:
        export_df = export_df.fillna("N/A")
        st.dataframe(export_df)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, sheet_name='Logs', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Logs']
            (max_row, max_col) = export_df.shape
            columns = [{'header': col} for col in export_df.columns]
            worksheet.add_table(0, 0, max_row, max_col - 1, {
                'columns': columns, 
                'style': 'Table Style Medium 9'
            })
        
        st.download_button(
            label="🚀 DOWNLOAD FOR ACCOUNTANT",
            data=buffer.getvalue(),
            file_name=f"Mileage_Report_{datetime.date.today()}.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.info("Log trips to enable export.")
