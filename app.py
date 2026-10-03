import os
import json
from datetime import datetime
import pytz
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# Scopes Definition
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Rates from Durga Puja 2026 Leaflet
DAILY_RATES = {
    "Full 4-Day Pack": {"VEG": 1100, "CHICKEN": 1240, "MUTTON": 1340},
    "Saptami (18 Oct)": {"VEG": 300, "CHICKEN": 350, "MUTTON": 350},
    "Ashtami (19 Oct)": {"VEG": 200, "CHICKEN": 200, "MUTTON": 200},
    "Nabami (20 Oct)": {"VEG": 300, "CHICKEN": 350, "MUTTON": 350},
    "Dashami (21 Oct)": {"VEG": 300, "CHICKEN": 340, "MUTTON": 440}
}
PARCEL_FEE = 40

st.set_page_config(
    page_title="HFCC Food Coupon Portal",
    page_icon="🌸",
    layout="wide"
)

# Responsive UI Style
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

def get_sheet_connections():
    # Robust parsing logic for Streamlit secrets
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    else:
        creds_json = st.secrets["GCP_SERVICE_ACCOUNT"]
        creds_dict = json.loads(creds_json)

    master_sheet_id = st.secrets["MASTER_SHEET_ID"]
    log_sheet_id = st.secrets["LOG_SHEET_ID"]
    master_tab = st.secrets.get("MASTER_TAB_NAME", "Subscription")
    log_tab = st.secrets.get("LOG_TAB_NAME", "DistributionLogs")
    
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    master_ws = client.open_by_key(master_sheet_id).worksheet(master_tab)
    log_ws = client.open_by_key(log_sheet_id).worksheet(log_tab)
    
    return master_ws, log_ws

st.title("🌸 HFCC Fortune Heights - Durga Puja 2026")
st.markdown("### 🎟 Food Coupon Issue & Distribution Management Portal")
st.markdown("---")

tab1, tab2 = st.tabs(["🎟 Issue Coupons", "📊 Sales Summary & Export"])

with tab1:
    st.markdown("#### 🔍 Step 1: Search & Verify Resident Subscription")
    col1, col2 = st.columns(2)
    with col1:
        block_input = st.text_input("BLOCK Name", placeholder="e.g. A")
    with col2:
        flat_input = st.text_input("FLAT Number", placeholder="e.g. 1008")
        
    if st.button("Search Master Record", type="primary"):
        if not block_input or not flat_input:
            st.warning("⚠️ Please enter both BLOCK Name and FLAT Number.")
        else:
            try:
                master_ws, _ = get_sheet_connections()
                records = master_ws.get_all_records()
                
                target_flat = str(flat_input).strip().lower()
                target_block = str(block_input).strip().lower()
                
                found = False
                for row in records:
                    b_val = str(row.get("BLOCK", "")).strip()
                    f_val = str(row.get("FLAT", "")).strip()
                    owner = str(row.get("NAME", "N/A")).strip()
                    sub_status = str(row.get("SUB_STATUS", "NO")).strip()
                    
                    if b_val.lower() == target_block and f_val.lower() == target_flat:
                        found = True
                        is_eligible = sub_status.upper() in ["YES", "PAID"]
                        
                        st.session_state["verified"] = is_eligible
                        st.session_state["owner_name"] = owner
                        st.session_state["block_val"] = b_val
                        st.session_state["flat_val"] = f_val
                        
                        if is_eligible:
                            st.success("✅ SUBSCRIPTION PAID & ELIGIBLE FOR FOOD COUPONS")
                        else:
                            st.error("❌ SUBSCRIPTION PENDING (SUB_STATUS: NO) - NOT ELIGIBLE")
                            
                        st.info(f"**Resident:** {owner} | **BLOCK:** {b_val} | **FLAT:** {f_val} | **SUB_STATUS:** {sub_status}")
                        break
                if not found:
                    st.session_state["verified"] = False
                    st.error("🔍 Record not found in Master Source Sheet.")
            except Exception as e:
                st.error(f"Connection Error: {str(e)}")

    if st.session_state.get("verified", False):
        st.markdown("---")
        st.markdown("#### 🎟 Step 2: Select Coupon & Issue Details")
        
        c1, c2 = st.columns(2)
        with c1:
            day_choice = st.selectbox("Meal Duration / Day", ["Full 4-Day Pack", "Saptami (18 Oct)", "Ashtami (19 Oct)", "Nabami (20 Oct)", "Dashami (21 Oct)"])
        with c2:
            cat_choice = st.selectbox("Food Category", ["Veg", "Non-Veg"])
            
        dashami_choice = "N/A"
        if day_choice == "Dashami (21 Oct)" and cat_choice == "Non-Veg":
            dashami_choice = st.radio("Dashami Non-Veg Type Choice", ["Chicken", "Mutton"], horizontal=True)
            
        c3, c4 = st.columns(2)
        with c3:
            parcel_choice = st.radio("Parcel Required?", ["No", "Yes"], horizontal=True)
        with c4:
            payment_choice = st.selectbox("Payment Mode", ["Cash", "Online"])
            
        serial_nos = st.text_input("Coupon Serial Numbers (Comma Separated)", placeholder="e.g. 101, 102, 103")

        if st.button("Confirm & Save Entries"):
            if not serial_nos:
                st.error("⚠️ Please enter Coupon Serial Numbers.")
            else:
                try:
                    _, log_ws = get_sheet_connections()
                    serials = [s.strip() for s in serial_nos.replace(";", ",").split(",") if s.strip()]
                    
                    cat_key = "VEG"
                    final_category_str = cat_choice
                    
                    if cat_choice == "Non-Veg":
                        if day_choice == "Dashami (21 Oct)":
                            cat_key = "MUTTON" if dashami_choice == "Mutton" else "CHICKEN"
                            final_category_str = f"Non-Veg ({dashami_choice})"
                        else:
                            cat_key = "CHICKEN"
                            
                    unit_food = DAILY_RATES[day_choice][cat_key]
                    unit_parcel = PARCEL_FEE if parcel_choice == "Yes" else 0
                    
                    tz = pytz.timezone('Asia/Kolkata')
                    now_ist = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
                    
                    rows = []
                    for serial in serials:
                        rows.append([
                            st.session_state["block_val"],
                            st.session_state["flat_val"],
                            st.session_state["owner_name"],
                            day_choice,
                            final_category_str,
                            parcel_choice,
                            serial,
                            unit_food,
                            unit_parcel,
                            payment_choice,
                            now_ist
                        ])
                    log_ws.append_rows(rows)
                    st.balloons()
                    st.success(f"🎉 Saved {len(rows)} coupon record(s) successfully to Distribution Log Sheet!")
                    st.session_state["verified"] = False
                except Exception as e:
                    st.error(f"Failed to save record: {str(e)}")

with tab2:
    st.markdown("#### 📊 Date Range Data Export & Sales Breakdown")
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        start_date = st.date_input("Start Date", datetime.now())
    with d_col2:
        end_date = st.date_input("End Date", datetime.now())
        
    if st.button("Generate Summary & Preview"):
        try:
            _, log_ws = get_sheet_connections()
            records = log_ws.get_all_records()
            if records:
                df = pd.DataFrame(records)
                df['Date_Only'] = pd.to_datetime(df['Distribution Timestamp']).dt.strftime('%Y-%m-%d')
                filtered_df = df[(df['Date_Only'] >= str(start_date)) & (df['Date_Only'] <= str(end_date))]
                
                if not filtered_df.empty:
                    st.markdown("### 📈 Distribution Summary Table")
                    st.dataframe(filtered_df, use_container_width=True)
                    
                    filtered_df['Food Amount'] = pd.to_numeric(filtered_df['Food Amount'], errors='coerce').fillna(0)
                    filtered_df['Parcel Amount'] = pd.to_numeric(filtered_df['Parcel Amount'], errors='coerce').fillna(0)
                    filtered_df['Total_Row_Amount'] = filtered_df['Food Amount'] + filtered_df['Parcel Amount']
                    
                    cash_total = filtered_df[filtered_df['Payment Mode'] == 'Cash']['Total_Row_Amount'].sum()
                    online_total = filtered_df[filtered_df['Payment Mode'] == 'Online']['Total_Row_Amount'].sum()
                    grand_total = filtered_df['Total_Row_Amount'].sum()
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Cash Collection", f"₹{cash_total}")
                    m2.metric("Online Collection", f"₹{online_total}")
                    m3.metric("Grand Total Collection", f"₹{grand_total}")
                else:
                    st.warning("No records found in this date range.")
            else:
                st.warning("No distribution records found.")
        except Exception as e:
            st.error(f"Error loading summary: {str(e)}")
