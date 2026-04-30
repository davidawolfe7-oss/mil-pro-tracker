import streamlit as st
import pandas as pd
import datetime
import sqlite3
import io
import math

# --- 1. DATABASE & LOGIC ---
def get_db_connection():
    conn = sqlite3.connect('milpro_tactical_v16.db', check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

conn = get_db_connection()
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trips 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, date_start TEXT, date_end TEXT, vehicle TEXT, 
              start_odo REAL, end_odo REAL, dist REAL, type TEXT, details TEXT, savings REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS garage 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, mpg REAL)''')
conn.commit()

RATES = {"Business": 0.725, "Medical": 0.22, "Charity": 0.14, "Personal": 0.0}

# --- 2. UI & THEME ---
st.set_page_config(page_title="Mil-Pro Command", layout="wide", page_icon="🦅")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    [data-testid="stMetric"] { background-color: #1f2937; border: 1px solid #3b82f6; border-radius: 10px; }
    .stButton>button { background-color: #1d4ed8 !important; color: white !important; font-weight: bold; width: 100%; height: 3.5em; }
    /* The Red Return Button */
    .return-btn > button { background-color: #B22234 !important; border: 2px solid white !important; height: 4em !important; font-size: 1.1rem !important; }
    .gps-btn > button { background-color: #10b981 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. GPS HELPER ---
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8  # Earth radius in miles
    dLat, dLon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

# --- 4. NAVIGATION STATE ---
if 'page' not in st.session_state: st.session_state.page = 'main'
if 'gps_running' not in st.session_state: st.session_state.gps_running = False

def navigate(page_name): st.session_state.page = page_name

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🦅 COMMAND")
    garage_df = pd.read_sql("SELECT * FROM garage ORDER BY name ASC", conn)
    active_v = st.selectbox("ACTIVE VEHICLE", garage_df['name'].tolist()) if not garage_df.empty else None
    
    with st.expander("➕ Add Vehicle"):
        n = st.text_input("Name")
        m = st.number_input("MPG", value=20.0)
        if st.button("Save Unit"):
            c.execute("INSERT INTO garage (name, mpg) VALUES (?,?)", (n, m)); conn.commit(); st.rerun()

# --- 6. MAIN DASHBOARD ---
if st.session_state.page == 'main':
    t1, t2, t3 = st.tabs(["🚀 Mission Log", "🎖️ IDT Tactical", "📊 Reports"])

    with t1:
        if active_v:
            st.subheader(f"Log Sortie: {active_v}")
            
            # --- GPS TOGGLE ---
            st.markdown("### 📡 GPS Tracking")
            if not st.session_state.gps_running:
                if st.button("🛰️ START TACTICAL GPS"):
                    st.session_state.gps_running = True
                    st.session_state.start_time = datetime.datetime.now()
                    # Placeholder for actual coordinates if browser supports it
                    st.session_state.start_coords = (43.9, -90.5) # Example: Tomah, WI
                    st.rerun()
            else:
                st.warning(f"MISSION ACTIVE since {st.session_state.start_time.strftime('%H:%M')}")
                if st.button("🏁 END MISSION & SYNC"):
                    st.session_state.gps_running = False
                    # Example distance calculation
                    end_coords = (43.8, -90.4) 
                    dist = haversine(st.session_state.start_coords[0], st.session_state.start_coords[1], end_coords[0], end_coords[1])
                    st.success(f"GPS Distance Synced: {round(dist, 2)} miles")
            
            st.divider()
            st.markdown("### ✍️ Manual Odometer Backup")
            last_q = pd.read_sql(f"SELECT end_odo FROM trips WHERE vehicle='{active_v}' ORDER BY id DESC LIMIT 1", conn)
            last_val = float(last_q['end_odo'].iloc[0]) if not last_q.empty else 0.0
            
            c1, c2 = st.columns(2)
            with c1: s_odo = st.number_input("Start Odo", value=last_val)
            with c2: e_odo = st.number_input("End Odo", value=s_odo + 1.0)
            
            cat = st.selectbox("Type", ["Business", "Medical", "Charity", "Personal"])
            if st.button("💾 SECURE DATA"):
                d = e_odo - s_odo
                val = d * RATES.get(cat, 0.0)
                c.execute("INSERT INTO trips (date_start, date_end, vehicle, start_odo, end_odo, dist, type, savings) VALUES (?,?,?,?,?,?,?,?)",
                          (datetime.date.today(), datetime.date.today(), active_v, s_odo, e_odo, d, cat, val))
                conn.commit(); st.success("Stored.")
        else: st.info("Register a vehicle in the sidebar.")

    with t2:
        st.subheader("🎖️ Full IDT Logistics")
        mode = st.radio("Mode", ["POV", "Flight", "Rental"], horizontal=True)
        c1, c2 = st.columns(2)
        with c1:
            idt_s = st.date_input("Start Date", datetime.date.today())
            idt_e = st.date_input("Through Date", datetime.date.today())
            gas = st.number_input("Gas ($)", min_value=0.0)
            tolls = st.number_input("Tolls ($)", min_value=0.0)
            parking = st.number_input("Airport/Hotel Parking ($)", min_value=0.0)
            lodging = st.number_input("Unreimbursed Lodging/Hotel ($)", min_value=0.0)
        with c2:
            reimb = st.number_input("Total Gov Payment ($)", value=750.0)
            mass_transit = st.number_input("Rideshare/Uber/Bus ($)", min_value=0.0)
            laundry = st.number_input("Laundry/Service (>50mi) ($)", min_value=0.0)
            
            if mode == "POV":
                mi = st.number_input("Total Miles", min_value=0.0)
                total = (mi * 0.725) + gas + tolls + parking + lodging + mass_transit + laundry
            elif mode == "Flight":
                f_c = st.number_input("Flight Ticket $", min_value=0.0)
                a_m = st.number_input("Airport Drive Miles", min_value=0.0)
                total = f_c + (a_m * 0.725) + gas + tolls + parking + lodging + mass_transit + laundry
            else:
                total = st.number_input("Rental $", min_value=0.0) + gas + tolls + parking + lodging + mass_transit + laundry
        
        net = max(0.0, total - reimb)
        st.metric("NET DEDUCTION", f"${net:.2f}")
        if st.button("🎖️ ARCHIVE FULL IDT"):
            c.execute("INSERT INTO trips (date_start, date_end, vehicle, dist, type, details, savings) VALUES (?,?,?,?,?,?,?)",
                      (idt_s, idt_e, "IDT-TACTICAL", 0, "Military IDT", f"{mode} | Tolls/Transit Inc.", net))
            conn.commit(); st.success("IDT Saved.")

    with t3:
        df = pd.read_sql("SELECT * FROM trips", conn)
        if not df.empty:
            st.metric("TOTAL ACCUMULATED SAVINGS", f"${df['savings'].sum():,.2f}")
            st.dataframe(df, use_container_width=True)
            st.button("🛠️ PREPARE FINAL EXPORT", on_click=navigate, args=['download'])

# --- 7. EXPORT SCREEN (THE "TRAP" FIX) ---
else:
    # This button is placed AT THE TOP and colored RED to ensure it is visible 
    # even when the phone's native "Save File" dialog pops up at the bottom.
    st.markdown('<div class="return-btn">', unsafe_allow_html=True)
    if st.button("🔙 EXIT EXPORT & RETURN TO DASHBOARD", on_click=navigate, args=['main']):
        pass
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    st.subheader("📩 Tactical Export Ready")
    
    df_export = pd.read_sql("SELECT * FROM trips", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False)
    
    st.download_button(label="💾 DOWNLOAD OFFICIAL REPORT", data=output.getvalue(), 
                       file_name=f"MilPro_Final_{datetime.date.today()}.xlsx")
