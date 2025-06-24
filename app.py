###############################################################################
# route_optimizer_v2.py – Streamlit interface + solver (UPDATED VERSION)
###############################################################################
import os
import io
import json
import time
from datetime import datetime, timedelta, date
from dateutil import parser as dtp

import pandas as pd
import streamlit as st
import googlemaps
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

# Import for Excel export
from io import BytesIO
import xlsxwriter

# Import for PDF export
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# --------------------------------------------------------------------------- #
# 1. USER INTERFACE
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Route Optimizer with Time‑Windows", layout="wide")
st.title("📍 Route Optimizer with Time Windows (Google Maps + OR‑Tools)")

# Sidebar – basic work‑day settings
with st.sidebar:
    st.header("🛠️ Work‑day parameters")
    
    # Time options for sidebar
    sidebar_time_options = []
    for hour in range(24):
        for minute in [0, 30]:
            if hour == 0:
                time_str = f"12:{minute:02d} AM"
            elif hour < 12:
                time_str = f"{hour}:{minute:02d} AM"
            elif hour == 12:
                time_str = f"12:{minute:02d} PM"
            else:
                time_str = f"{hour-12}:{minute:02d} PM"
            sidebar_time_options.append(time_str)
    
    work_start_str = st.selectbox("Work day starts", 
                                  options=sidebar_time_options,
                                  index=sidebar_time_options.index("9:00 AM"))
    work_start = datetime.strptime(work_start_str, "%I:%M %p").time()
    
    work_end_str = st.selectbox("Work day ends", 
                                options=sidebar_time_options,
                                index=sidebar_time_options.index("5:00 PM"))
    work_end = datetime.strptime(work_end_str, "%I:%M %p").time()
    
    work_days = st.multiselect(
        "Working days", 
        options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        format_func=lambda x: x
    )
    # Convert to numeric days
    days_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, 
                "Friday": 4, "Saturday": 5, "Sunday": 6}
    work_days = [days_map[day] for day in work_days]
    
    service_min = st.number_input("Service / inspection duration (minutes)", 1, 240, 30)
    depot_addr  = st.text_input("Start / end address (depot)", "")

st.markdown("### 1️⃣ Enter visits")
tab1, tab2 = st.tabs(["Upload Excel / Sheets", "Type manually"])

# ––– 1A. Excel upload ––– #
if "input_df" not in st.session_state:
    st.session_state.input_df = pd.DataFrame({
        "Address": [""],
        "WindowStart": ["9:00 AM"],
        "WindowEnd": ["10:00 AM"],
        "AllowedDays": ["0,1,2,3,4"],
        "BlackoutDates": [""]
    })

with tab1:
    # Sample file downloads section
    st.info("📋 **Required Headers**: Address, WindowStart, WindowEnd, AllowedDays, BlackoutDates")
    
    with st.expander("📥 Download Sample Templates"):
        col1, col2, col3 = st.columns(3)
        
        # Create sample data
        sample_data = pd.DataFrame({
            "Address": [
                "123 Main St, New York, NY 10001",
                "456 Park Ave, New York, NY 10002",
                "789 Broadway, New York, NY 10003"
            ],
            "WindowStart": ["9:00 AM", "10:00 AM", "2:00 PM"],
            "WindowEnd": ["11:00 AM", "12:00 PM", "4:00 PM"],
            "AllowedDays": ["0,1,2,3,4", "1,2,3,4,5", "0,1,2,3,4"],  # 0=Mon, 1=Tue, etc.
            "BlackoutDates": ["", "12/25/2024, 12/26/2024", ""]
        })
        
        # Excel sample
        with col1:
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                sample_data.to_excel(writer, sheet_name='Visits', index=False)
                
                # Add instructions sheet
                instructions = pd.DataFrame({
                    'Column': ['Address', 'WindowStart', 'WindowEnd', 'AllowedDays', 'BlackoutDates'],
                    'Description': [
                        'Full address including street, city, state, zip',
                        'Time in format like "9:00 AM" or "2:30 PM"',
                        'Time in format like "11:00 AM" or "4:30 PM"',
                        'Comma-separated days: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun',
                        'Comma-separated dates in MM/DD/YYYY format (optional)'
                    ],
                    'Example': [
                        '123 Main St, New York, NY 10001',
                        '9:00 AM',
                        '11:00 AM',
                        '0,1,2,3,4',
                        '12/25/2024, 12/26/2024'
                    ]
                })
                instructions.to_excel(writer, sheet_name='Instructions', index=False)
            
            excel_data = excel_buffer.getvalue()
            st.download_button(
                "📊 Excel Template",
                excel_data,
                "route_template.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Download Excel template with sample data"
            )
        
        # CSV sample
        with col2:
            csv_data = sample_data.to_csv(index=False).encode()
            st.download_button(
                "📄 CSV Template",
                csv_data,
                "route_template.csv",
                "text/csv",
                help="Download CSV template with sample data"
            )
        
        # TXT sample with instructions
        with col3:
            txt_content = "ROUTE OPTIMIZER TEMPLATE - INSTRUCTIONS\n"
            txt_content += "="*50 + "\n\n"
            txt_content += "Required columns (must be in first row):\n"
            txt_content += "Address,WindowStart,WindowEnd,AllowedDays,BlackoutDates\n\n"
            txt_content += "Column Descriptions:\n"
            txt_content += "-"*30 + "\n"
            txt_content += "Address: Full address including street, city, state, zip\n"
            txt_content += "WindowStart: Time in 12-hour format (e.g., 9:00 AM)\n"
            txt_content += "WindowEnd: Time in 12-hour format (e.g., 11:00 AM)\n"
            txt_content += "AllowedDays: Days as numbers (0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun)\n"
            txt_content += "BlackoutDates: Dates in MM/DD/YYYY format, comma-separated\n\n"
            txt_content += "Example data:\n"
            txt_content += "-"*30 + "\n"
            txt_content += sample_data.to_csv(index=False)
            
            st.download_button(
                "📝 TXT Instructions",
                txt_content.encode(),
                "route_template_instructions.txt",
                "text/plain",
                help="Download instructions and template in text format"
            )
    
    st.markdown("---")
    
    # File uploader
    up_file = st.file_uploader(
        "Upload your file (.xlsx, .xls, .xlsm, or .csv)",
        type=["xlsx", "xlsm", "xls", "csv"],
        help="Upload a file with the required headers: Address, WindowStart, WindowEnd, AllowedDays, BlackoutDates"
    )
    
    if up_file:
        try:
            if up_file.name.endswith('.csv'):
                uploaded_df = pd.read_csv(up_file)
            else:
                uploaded_df = pd.read_excel(up_file)
            
            # Check for required columns
            required_columns = ["Address", "WindowStart", "WindowEnd", "AllowedDays", "BlackoutDates"]
            missing_columns = [col for col in required_columns if col not in uploaded_df.columns]
            
            if missing_columns:
                st.error(f"❌ Missing required columns: {', '.join(missing_columns)}")
                st.info("Please ensure your file has all required columns. Download a sample template above for reference.")
            else:
                st.session_state.input_df = uploaded_df
                st.success(f"✅ Loaded {len(uploaded_df)} rows from {up_file.name}")
                
                # Show preview of loaded data
                with st.expander("Preview loaded data"):
                    st.dataframe(uploaded_df.head())
        except Exception as e:
            st.error(f"❌ Error reading file: {str(e)}")
            st.info("Please ensure your file is in the correct format. Download a sample template above for reference.")

# ––– 1B. Manual entry ––– #
with tab2:
    # Generate time options in standard format
    time_options = []
    for hour in range(24):
        for minute in [0, 30]:
            if hour == 0:
                time_str = f"12:{minute:02d} AM"
            elif hour < 12:
                time_str = f"{hour}:{minute:02d} AM"
            elif hour == 12:
                time_str = f"12:{minute:02d} PM"
            else:
                time_str = f"{hour-12}:{minute:02d} PM"
            time_options.append(time_str)
    
    # Days of week mapping
    days_mapping = {
        "Monday": "0",
        "Tuesday": "1", 
        "Wednesday": "2",
        "Thursday": "3",
        "Friday": "4",
        "Saturday": "5",
        "Sunday": "6"
    }
    
    # Create editable dataframe with custom columns
    num_rows = len(st.session_state.input_df)
    
    # Add row button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("➕ Add Row"):
            new_row = pd.DataFrame({
                "Address": [""],
                "WindowStart": ["9:00 AM"],
                "WindowEnd": ["10:00 AM"],
                "AllowedDays": ["0,1,2,3,4"],
                "BlackoutDates": [""]
            })
            st.session_state.input_df = pd.concat([st.session_state.input_df, new_row], ignore_index=True)
            st.rerun()
    
    # Create form for each row
    updated_data = []
    for idx, row in st.session_state.input_df.iterrows():
        with st.container():
            cols = st.columns([3, 1.5, 1.5, 2, 2, 0.5])
            
            # Address
            address = cols[0].text_input(
                "Address" if idx == 0 else "",
                value=row.get("Address", ""),
                key=f"addr_{idx}"
            )
            
            # Window Start
            start_default = row.get("WindowStart", "9:00 AM")
            if start_default not in time_options:
                start_default = "9:00 AM"
            window_start = cols[1].selectbox(
                "Window Start" if idx == 0 else " ",  # Single space instead of empty
                options=time_options,
                index=time_options.index(start_default),
                key=f"start_{idx}",
                label_visibility="visible" if idx == 0 else "hidden"
            )
            
            # Window End
            end_default = row.get("WindowEnd", "10:00 AM")
            if end_default not in time_options:
                end_default = "10:00 AM"
            window_end = cols[2].selectbox(
                "Window End" if idx == 0 else " ",  # Single space instead of empty
                options=time_options,
                index=time_options.index(end_default),
                key=f"end_{idx}",
                label_visibility="visible" if idx == 0 else "hidden"
            )
            
            # Allowed Days
            current_days = str(row.get("AllowedDays", "0,1,2,3,4")).split(",")
            selected_days = []
            for day, val in days_mapping.items():
                if val in current_days:
                    selected_days.append(day)
            
            allowed_days = cols[3].multiselect(
                "Allowed Days" if idx == 0 else " ",  # Single space instead of empty
                options=list(days_mapping.keys()),
                default=selected_days,
                key=f"days_{idx}",
                label_visibility="visible" if idx == 0 else "hidden"
            )
            allowed_days_str = ",".join([days_mapping[day] for day in allowed_days])
            
            # Blackout Dates
            blackout = cols[4].text_input(
                "Blackout Dates" if idx == 0 else " ",  # Single space instead of empty
                value=row.get("BlackoutDates", ""),
                placeholder="MM/DD/YYYY, MM/DD/YYYY",
                key=f"blackout_{idx}",
                label_visibility="visible" if idx == 0 else "hidden"
            )
            
            # Delete button
            if idx > 0 or len(st.session_state.input_df) > 1:
                if cols[5].button("🗑️", key=f"del_{idx}"):
                    st.session_state.input_df = st.session_state.input_df.drop(index=idx).reset_index(drop=True)
                    st.rerun()
            
            updated_data.append({
                "Address": address,
                "WindowStart": window_start,
                "WindowEnd": window_end,
                "AllowedDays": allowed_days_str,
                "BlackoutDates": blackout
            })
    
    # Update session state with new data
    st.session_state.input_df = pd.DataFrame(updated_data)

df_raw = st.session_state.input_df.copy()

# Filter out empty rows
df_raw = df_raw[df_raw['Address'].str.strip() != '']

# Show current data status
if not df_raw.empty:
    st.success(f"✅ {len(df_raw)} visits loaded")

if df_raw.empty:
    st.warning("⚠️ Please enter at least one visit to optimize routes.")
    st.stop()

# --------------------------------------------------------------------------- #
# SHOW THE RUN OPTIMIZATION BUTTON PROMINENTLY
# --------------------------------------------------------------------------- #
st.markdown("---")
st.markdown("### 2️⃣ Run Route Optimization")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    run_button = st.button(
        "🚀 Run Route Optimization", 
        type="primary", 
        use_container_width=True,
        help="Click to optimize your route based on the entered visits"
    )

if not run_button:
    st.info("👆 Click the button above to optimize your route after entering visit data.")
    st.stop()

# Check for depot address
if not depot_addr or depot_addr.strip() == "":
    st.error("⚠️ Please enter a depot address (Start / end address) in the sidebar before optimizing.")
    st.info("The depot address is required to calculate routes from your starting location.")
    st.stop()

# Get Google Maps API key
def get_google_maps_api_key():
    # First try to get from Streamlit secrets (for deployment)
    if hasattr(st, 'secrets') and 'GOOGLE_MAPS_API_KEY' in st.secrets:
        return st.secrets['GOOGLE_MAPS_API_KEY']
    # Fall back to environment variable (for local development)
    return os.getenv('GOOGLE_MAPS_API_KEY')

api_key = get_google_maps_api_key()
if not api_key:
    st.error("⚠️ Google Maps API key not found!")
    st.code("export GOOGLE_MAPS_API_KEY='your_api_key_here'", language="bash")
    st.info("Please set the GOOGLE_MAPS_API_KEY environment variable for local development or add it to Streamlit secrets for deployment.")
    st.stop()

# --------------------------------------------------------------------------- #
# 2. VALIDATION & PRE‑PROCESSING
# --------------------------------------------------------------------------- #
def parse_time(s: str) -> datetime.time:
    """Parse time string in standard format (e.g., '9:30 AM' or '2:30 PM')"""
    try:
        # Handle standard time format
        time_obj = datetime.strptime(s, "%I:%M %p")
        return time_obj.time()
    except:
        # Fallback to 24-hour format if needed
        try:
            return dtp.parse(s).time()
        except:
            raise ValueError(f"Invalid time format: {s}")

def parse_date_list(s: str) -> set[date]:
    if pd.isna(s) or not str(s).strip() or str(s).lower() == 'nan':
        return set()
    try:
        dates = set()
        for tok in str(s).split(","):
            tok = tok.strip()
            if tok and tok.lower() != 'nan':
                dates.add(dtp.parse(tok).date())
        return dates
    except Exception as e:
        st.warning(f"Could not parse date: {s}. Error: {str(e)}")
        return set()

errors = []
for i, row in df_raw.iterrows():
    for col in ["Address", "WindowStart", "WindowEnd"]:
        if pd.isna(row[col]) or str(row[col]).strip() == "":
            errors.append(f"Row {i+1}: '{col}' is required.")
    try:
        start_time = parse_time(row["WindowStart"])
        end_time = parse_time(row["WindowEnd"])
        
        # Check if end time is before start time
        if end_time <= start_time:
            errors.append(f"Row {i+1}: Window End ({row['WindowEnd']}) must be after Window Start ({row['WindowStart']})")
    except Exception:
        errors.append(f"Row {i+1}: invalid time window format.")

if errors:
    st.error("⚠️ Data issues:\n" + "\n".join(errors))
    st.stop()

# Expand repeating constraints into concrete daily time‑windows ----------------
def expand_rows(row):
    address       = row["Address"]
    win_start     = parse_time(row["WindowStart"])
    win_end       = parse_time(row["WindowEnd"])
    # Parse allowed days, handling 'nan' and empty values
    allowed_days_str = str(row.get("AllowedDays", ""))
    if allowed_days_str.lower() == 'nan' or not allowed_days_str.strip():
        allowed_days = set(range(7))  # Default to all days
    else:
        allowed_days = {int(d.strip()) for d in allowed_days_str.split(",") if d.strip().isdigit()} or set(range(7))
    blackout      = parse_date_list(row.get("BlackoutDates",""))

    today = date.today()
    
    # Find the next available work day that's allowed
    for d in range(7):  # Look up to 7 days ahead
        day_date = today + timedelta(days=d)
        if (day_date.weekday() in allowed_days and 
            day_date not in blackout and 
            day_date.weekday() in work_days):
            # Return just one visit per address on the first available day
            return {
                "Address": address,
                "WindowStartDT": datetime.combine(day_date, win_start),
                "WindowEndDT": datetime.combine(day_date, win_end)
            }
    
    # If no valid day found, return None
    return None

# Get the optimization date from sidebar work days selection
# This should be the first selected work day
if work_days:
    # Find the next occurrence of the first selected work day
    today = date.today()
    days_ahead = (work_days[0] - today.weekday()) % 7
    if days_ahead == 0 and datetime.now().time() > work_end:
        days_ahead = 7  # If today is the day but past work hours, go to next week
    optimization_date = today + timedelta(days=days_ahead)
else:
    st.error("Please select at least one work day in the sidebar.")
    st.stop()

st.info(f"📅 Optimizing route for {optimization_date.strftime('%A, %B %d, %Y')}")

# Process visits - only include those that can be scheduled on the optimization date
visits_list = []
for _, row in df_raw.iterrows():
    address = row.get("Address", "")
    win_start = parse_time(row.get("WindowStart", ""))
    win_end = parse_time(row.get("WindowEnd", ""))
    allowed_days_str = str(row.get("AllowedDays", ""))
    
    # Parse allowed days
    if allowed_days_str.lower() == 'nan' or not allowed_days_str.strip():
        allowed_days = set(range(7))  # Default to all days
    else:
        allowed_days = {int(d.strip()) for d in allowed_days_str.split(",") if d.strip().isdigit()} or set(range(7))
    
    # Check if optimization date is an allowed day for this visit
    if optimization_date.weekday() in allowed_days:
        # Check if it's not a blackout date
        blackout = parse_date_list(row.get("BlackoutDates",""))
        if optimization_date not in blackout:
            visits_list.append({
                "Address": address,
                "WindowStartDT": datetime.combine(optimization_date, win_start),
                "WindowEndDT": datetime.combine(optimization_date, win_end)
            })

visits = pd.DataFrame(visits_list)
if visits.empty:
    st.warning(f"No visits can be scheduled on {optimization_date.strftime('%A, %B %d, %Y')}. Check allowed days and blackout dates.")
    st.stop()

with st.spinner("🔄 Optimizing route..."):
    # --------------------------------------------------------------------------- #
    # 3. DISTANCE / DURATION MATRIX FROM GOOGLE MAPS
    # --------------------------------------------------------------------------- #
    gmaps = googlemaps.Client(key=api_key)
    all_addresses = [depot_addr] + visits["Address"].tolist()
    N = len(all_addresses)
    
    # Check if we have too many addresses
    if N > 25:
        st.warning(f"⚠️ You have {N} addresses (including depot). Google Maps API has limits on the number of addresses. Consider reducing to 25 or fewer for best results.")
    
    # Show address count
    st.info(f"📍 Calculating routes for {N-1} visits plus depot location")

    @st.cache_data(show_spinner="Calling Distance Matrix API…")
    def build_duration_matrix(addresses):
        """Return N×N matrix in seconds."""
        matrix = [[0]*N for _ in range(N)]
        
        # Use smaller chunks to avoid API limits
        # Google's Distance Matrix API limits: 
        # - 100 elements per request (origins × destinations)
        # - 25 origins or 25 destinations per request
        # We'll use 3x3 = 9 elements to be very safe
        CHUNK = 3
        
        total_requests = ((N + CHUNK - 1) // CHUNK) ** 2
        if total_requests > 1:
            progress_bar = st.progress(0, text="Calculating distances...")
        else:
            progress_bar = None
        request_count = 0
        
        try:
            for i in range(0, N, CHUNK):
                for j in range(0, N, CHUNK):
                    origins      = addresses[i:i+CHUNK]
                    destinations = addresses[j:j+CHUNK]
                    
                    # Update progress
                    request_count += 1
                    if progress_bar:
                        progress = request_count / total_requests
                        progress_bar.progress(progress, 
                            text=f"Calculating distances... ({request_count}/{total_requests} requests)")
                    
                    try:
                        resp = gmaps.distance_matrix(
                            origins, destinations,
                            mode="driving", units="imperial"
                        )
                    except Exception as api_error:
                        st.error(f"Google Maps API request failed: {str(api_error)}")
                        if "MAX_ELEMENTS_EXCEEDED" in str(api_error):
                            st.info("Try reducing the number of visits or contact support for API limits.")
                        return None
                    
                    if resp['status'] != 'OK':
                        st.error(f"Google Maps API error: {resp.get('error_message', 'Unknown error')}")
                        return None
                    
                    rows = resp["rows"]
                    for oi, row in enumerate(rows):
                        for di, elem in enumerate(row["elements"]):
                            if elem['status'] == 'OK':
                                dur = elem.get("duration", {}).get("value", 0)
                                matrix[i+oi][j+di] = dur
                            else:
                                # Handle cases where no route exists
                                st.warning(f"No route found from {origins[oi]} to {destinations[di]}")
                                matrix[i+oi][j+di] = 999999  # Large number instead of infinity
            
            if progress_bar:
                progress_bar.empty()
            return matrix
            
        except Exception as e:
            if progress_bar:
                progress_bar.empty()
            if "MAX_ELEMENTS_EXCEEDED" in str(e):
                st.error("⚠️ Too many addresses for Google Maps API limits. Please reduce the number of visits or upgrade your API plan.")
            elif "REQUEST_DENIED" in str(e):
                st.error("⚠️ Google Maps API request denied. Please check your API key and ensure Distance Matrix API is enabled.")
            else:
                st.error(f"⚠️ Google Maps API error: {str(e)}")
            return None

    dur_matrix = build_duration_matrix(all_addresses)
    
    if dur_matrix is None:
        st.stop()

    # --------------------------------------------------------------------------- #
    # 4. OR‑TOOLS VRPTW MODEL
    # --------------------------------------------------------------------------- #
    # Calculate depot start and end times globally for error handling
    first_day = optimization_date
    depot_start = datetime.combine(first_day, work_start)
    depot_end = datetime.combine(first_day, work_end)
    
    def create_data_model():
        data = {}
        data["time_matrix"] = dur_matrix
        data["service_times"] = [0] + [service_min*60]*len(visits)   # depot 0 sec
        data["time_windows"] = []
        
        # Depot window - can leave anytime during work hours
        depot_window_start = 0  # Start of work day
        depot_window_end = int((depot_end - depot_start).total_seconds())
        data["time_windows"].append((depot_window_start, depot_window_end))
        
        # Visit time windows - convert to seconds from start of work day
        for i, v in visits.iterrows():
            visit_start = int((v["WindowStartDT"] - depot_start).total_seconds())
            visit_end = int((v["WindowEndDT"] - depot_start).total_seconds())
            
            # Ensure windows are within work hours
            visit_start = max(0, visit_start)  # Can't be before work starts
            visit_end = min(depot_window_end, visit_end)  # Can't be after work ends
            
            # IMPORTANT: Adjust end time to ensure service can be completed within window
            # The arrival must be early enough to complete service before window end
            service_seconds = service_min * 60
            
            # Latest arrival time is window_end - service_time
            # This ensures service can be completed within the time window
            adjusted_end = visit_end - service_seconds
            
            # Make sure the adjusted window is still valid
            if adjusted_end < visit_start:
                # If service time is longer than the window, we can't visit this location
                st.warning(f"⚠️ Location {i+1} has a time window shorter than service time!")
                adjusted_end = visit_start  # This will likely cause the visit to be dropped
            
            data["time_windows"].append((visit_start, adjusted_end))
        
        data["num_vehicles"] = 1
        data["depot"] = 0
        return data

    data = create_data_model()

    # Build the Routing Index Manager and Model
    manager = pywrapcp.RoutingIndexManager(len(data["time_matrix"]),
                                           data["num_vehicles"],
                                           data["depot"])
    routing = pywrapcp.RoutingModel(manager)

    # --- Time callback
    def time_callback(from_index, to_index):
        """Travel + service time between nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node   = manager.IndexToNode(to_index)
        travel = data["time_matrix"][from_node][to_node]
        
        # Only add service time if we're leaving a non-depot node
        if from_node == 0:  # Depot has no service time
            return travel
        else:
            return travel + data["service_times"][from_node]

    transit_callback_idx = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_idx)

    # --- Add time‑window constraints
    # Calculate work day duration in seconds
    work_day_seconds = int((depot_end - depot_start).total_seconds())
    
    routing.AddDimension(
        transit_callback_idx,
        slack_max=60*60,                           # 1 hour waiting allowed
        capacity=work_day_seconds,                 # Work day duration
        fix_start_cumul_to_zero=False,            # Allow flexible start time
        name="Time"
    )
    time_dim = routing.GetDimensionOrDie("Time")
    
    # Minimize the start time of routes (prefer later departures)
    for vehicle_id in range(data["num_vehicles"]):
        start_index = routing.Start(vehicle_id)
        time_dim.SetCumulVarSoftLowerBound(start_index, 0, 10000)
    
    # Minimize total time to avoid unnecessary waiting
    time_dim.SetGlobalSpanCostCoefficient(1)
    
    # Add HARD time window constraints
    for idx, (start, end) in enumerate(data["time_windows"]):
        node_index = manager.NodeToIndex(idx)
        
        # Set hard time window constraints
        try:
            time_dim.CumulVar(node_index).SetRange(int(start), int(end))
        except Exception as e:
            st.error(f"Failed to set time window for location {idx}: {e}")
            # For debugging, show the problematic window
            if idx > 0:
                st.write(f"Visit {idx-1}: {visits.iloc[idx-1]['Address']}")
                st.write(f"Arrival window: {start} - {end} seconds from work start")
                st.write(f"Service time: {service_min * 60} seconds")
                st.write(f"Note: Latest arrival is adjusted to ensure service completes within window")
    
    # Force vehicle to return to depot before work day ends
    end_index = routing.End(0)
    time_dim.CumulVar(end_index).SetMax(work_day_seconds)

    # ALLOW DROPPING VISITS - this is the key change!
    # Add a penalty for dropping nodes but allow it
    penalty = 1000000  # High penalty but not infinite
    for node in range(1, len(data["time_matrix"])):  # Skip depot (node 0)
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    # --- Search parameters
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)  # Better for time windows
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_params.time_limit.seconds = 60  # Increased from 30 seconds
    
    # Remove the soft bound penalties since we're allowing drops
    # for idx in range(1, len(data["time_windows"])):
    #     node_index = manager.NodeToIndex(idx)
    #     time_dim.SetCumulVarSoftUpperBound(node_index, data["time_windows"][idx][1], 100000)
    #     time_dim.SetCumulVarSoftLowerBound(node_index, data["time_windows"][idx][0], 100000)

    # --------------------------------------------------------------------------- #
    # 5. SOLVE
    # --------------------------------------------------------------------------- #
    st.info("🔍 Running optimization solver...")
    solution = routing.SolveWithParameters(search_params)
    
    if not solution:
        st.error("❌ No solution found within 60 seconds.")
        st.info("💡 This usually means the problem is over-constrained. The solver couldn't find a valid route even when allowing visits to be skipped.")
        
        # Debug information
        with st.expander("🔍 Debug Information"):
            st.write(f"Number of locations: {N}")
            st.write(f"Work hours: {work_start_str} - {work_end_str}")
            st.write("Time windows (adjusted for service time):")
            for idx, (s, e) in enumerate(data["time_windows"]):
                if idx == 0:
                    st.write(f"  Depot: 0 - {e} seconds")
                else:
                    # Show both original and adjusted windows for clarity
                    orig_start = visits.iloc[idx-1]['WindowStartDT']
                    orig_end = visits.iloc[idx-1]['WindowEndDT']
                    st.write(f"  Visit {idx}: {s} - {e} seconds (arrival window)")
                    st.write(f"    Original window: {orig_start.strftime('%I:%M %p')} - {orig_end.strftime('%I:%M %p')}")
                    st.write(f"    Must arrive by: {(depot_start + timedelta(seconds=e)).strftime('%I:%M %p')} to complete {service_min} min service")
            st.write("\nPossible issues:")
            st.write("- Time windows might be too narrow after accounting for service time")
            st.write("- Travel times between locations might be too long")
            st.write("- Some locations may have windows shorter than service time")
        st.stop()

    # --------------------------------------------------------------------------- #
    # 6. PROCESS RESULTS AND STORE IN SESSION STATE
    # --------------------------------------------------------------------------- #
    
    # Track which nodes are visited
    visited_nodes = set()
    route = []
    index = routing.Start(0)
    cum = time_dim.CumulVar(index)
    
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        visited_nodes.add(node)
        
        # Calculate actual arrival time
        time_value = solution.Value(time_dim.CumulVar(index))
        arr_ts = depot_start + timedelta(seconds=time_value)
        
        if node == 0:
            label = "🏢 Depot (Start)"
            service_time = 0
        else:
            label = f"📍 {visits.iloc[node-1]['Address']}"
            service_time = service_min
        
        # Format arrival time in standard format (AM/PM)
        arrival_str = arr_ts.strftime("%I:%M %p").lstrip('0')
        
        # Calculate time since start
        if len(route) == 0:
            time_from_start = "Start"
        else:
            minutes_from_start = int(time_value / 60)
            time_from_start = f"+{minutes_from_start} min"
        
        route.append({
            "Stop #": len(route),
            "Location": label,
            "Arrival": arrival_str,
            "Service Time": f"{service_time} min" if service_time > 0 else "-",
            "Time from Start": time_from_start
        })
        
        index = solution.Value(routing.NextVar(index))
    
    # Add final return to depot
    node = manager.IndexToNode(index)
    end_time_value = solution.Value(time_dim.CumulVar(routing.End(0)))
    arr_ts = depot_start + timedelta(seconds=end_time_value)
    arrival_str = arr_ts.strftime("%I:%M %p").lstrip('0')
    minutes_from_start = int(end_time_value / 60)
    
    route.append({
        "Stop #": len(route),
        "Location": "🏢 Depot (End)",
        "Arrival": arrival_str,
        "Service Time": "-",
        "Time from Start": f"+{minutes_from_start} min"
    })
    
    # Find unassigned locations
    unassigned_locations = []
    for idx in range(1, len(visits) + 1):
        if idx not in visited_nodes:
            unassigned_locations.append({
                "Address": visits.iloc[idx-1]['Address'],
                "Window Start": visits.iloc[idx-1]['WindowStartDT'].strftime("%I:%M %p").lstrip('0'),
                "Window End": visits.iloc[idx-1]['WindowEndDT'].strftime("%I:%M %p").lstrip('0'),
                "Reason": "Could not fit within time/distance constraints"
            })
    
    # Store results in session state
    st.session_state.route_df = pd.DataFrame(route)
    st.session_state.unassigned_df = pd.DataFrame(unassigned_locations) if unassigned_locations else pd.DataFrame()
    
    # Calculate total time accounting for early departure
    end_time_raw = solution.Value(time_dim.CumulVar(routing.End(0)))
    st.session_state.total_time = int(end_time_raw / 60)
    
    st.session_state.total_service = service_min * (len(visited_nodes) - 1)  # Exclude depot
    st.session_state.total_travel = st.session_state.total_time - st.session_state.total_service
    st.session_state.optimization_date = optimization_date
    st.session_state.depot_address = depot_addr
    st.session_state.has_results = True
    st.session_state.data = data  # Store data for access in display section

# --------------------------------------------------------------------------- #
# 7. DISPLAY RESULTS (From Session State)
# --------------------------------------------------------------------------- #
if 'has_results' in st.session_state and st.session_state.has_results:
    st.markdown("---")
    st.markdown("### 3️⃣ Optimized Route Results")
    st.success("✅ Route optimization completed successfully!")
    
    # Add explanation about timing
    with st.expander("ℹ️ Understanding the Schedule"):
        info_text = """
        **How timing works:**
        - **Arrival Time**: When you arrive at each location
        - **Service Time**: How long you spend at each location (inspection/service duration)
        - **Travel Time**: Actual driving time between locations
        
        **Important Time Window Constraint:**
        The optimizer ensures you can complete the service within the time window.
        For example, if a window ends at 10:00 AM and service takes 30 minutes,
        you must arrive by 9:30 AM or earlier.
        
        The optimizer considers both travel time AND service time when planning your route.
        So if you see a gap between stops, it includes:
        - Service time at the previous location
        - Plus actual travel time to the next location
        """
        
        st.info(info_text)
    
    # Display route
    st.dataframe(st.session_state.route_df, use_container_width=True)
    
    # Show summary statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Time", f"{st.session_state.total_time} minutes")
    with col2:
        st.metric("Travel Time", f"{st.session_state.total_travel} minutes")
    with col3:
        st.metric("Service Time", f"{st.session_state.total_service} minutes")
    
    # Show unassigned locations if any
    if not st.session_state.unassigned_df.empty:
        st.markdown("---")
        st.markdown("### ⚠️ Unassigned Locations")
        st.warning(f"{len(st.session_state.unassigned_df)} location(s) could not be included in the route due to time/distance constraints:")
        st.dataframe(st.session_state.unassigned_df, use_container_width=True)
    
    # Export options
    st.markdown("---")
    st.markdown("### 📥 Export Options")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # CSV Export
    with col1:
        csv_data = st.session_state.route_df.to_csv(index=False).encode()
        st.download_button(
            "⬇️ Download CSV",
            csv_data,
            f"optimized_route_{st.session_state.optimization_date.strftime('%Y%m%d')}.csv",
            "text/csv",
            key="csv_download"
        )
    
    # Excel Export
    with col2:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            st.session_state.route_df.to_excel(writer, sheet_name='Route', index=False)
            if not st.session_state.unassigned_df.empty:
                st.session_state.unassigned_df.to_excel(writer, sheet_name='Unassigned', index=False)
            
            # Add summary sheet
            summary_data = {
                'Metric': ['Optimization Date', 'Depot Address', 'Total Time (minutes)', 
                          'Travel Time (minutes)', 'Service Time (minutes)', 'Locations Visited', 
                          'Locations Unassigned'],
                'Value': [st.session_state.optimization_date.strftime('%Y-%m-%d'),
                         st.session_state.depot_address,
                         st.session_state.total_time,
                         st.session_state.total_travel,
                         st.session_state.total_service,
                         len(st.session_state.route_df) - 2,  # Exclude depot start/end
                         len(st.session_state.unassigned_df)]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        excel_data = output.getvalue()
        st.download_button(
            "📊 Download Excel",
            excel_data,
            f"optimized_route_{st.session_state.optimization_date.strftime('%Y%m%d')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="excel_download"
        )
    
    # TXT Export
    with col3:
        txt_content = f"ROUTE OPTIMIZATION REPORT\n"
        txt_content += f"{'='*50}\n\n"
        txt_content += f"Date: {st.session_state.optimization_date.strftime('%A, %B %d, %Y')}\n"
        txt_content += f"Depot: {st.session_state.depot_address}\n\n"
        txt_content += f"SUMMARY\n{'-'*20}\n"
        txt_content += f"Total Time: {st.session_state.total_time} minutes\n"
        txt_content += f"Travel Time: {st.session_state.total_travel} minutes\n"
        txt_content += f"Service Time: {st.session_state.total_service} minutes\n"
        txt_content += f"Locations Visited: {len(st.session_state.route_df) - 2}\n"
        txt_content += f"Locations Unassigned: {len(st.session_state.unassigned_df)}\n\n"
        txt_content += f"ROUTE DETAILS\n{'-'*20}\n"
        
        for _, row in st.session_state.route_df.iterrows():
            txt_content += f"{row['Stop #']:2d}. {row['Location']:<40} "
            txt_content += f"Arrival: {row['Arrival']:<8} "
            txt_content += f"Service: {row['Service Time']:<6} "
            txt_content += f"Time: {row['Time from Start']}\n"
        
        if not st.session_state.unassigned_df.empty:
            txt_content += f"\nUNASSIGNED LOCATIONS\n{'-'*20}\n"
            for _, row in st.session_state.unassigned_df.iterrows():
                txt_content += f"- {row['Address']} (Window: {row['Window Start']} - {row['Window End']})\n"
        
        st.download_button(
            "📄 Download TXT",
            txt_content.encode(),
            f"optimized_route_{st.session_state.optimization_date.strftime('%Y%m%d')}.txt",
            "text/plain",
            key="txt_download"
        )
    
    # PDF Export (if available)
    with col4:
        if REPORTLAB_AVAILABLE:
            # Create PDF
            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            # Title
            title = Paragraph(f"Route Optimization Report", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 12))
            
            # Summary info
            summary_text = f"<b>Date:</b> {st.session_state.optimization_date.strftime('%A, %B %d, %Y')}<br/>"
            summary_text += f"<b>Depot:</b> {st.session_state.depot_address}<br/>"
            summary_text += f"<b>Total Time:</b> {st.session_state.total_time} minutes<br/>"
            summary_text += f"<b>Travel Time:</b> {st.session_state.total_travel} minutes<br/>"
            summary_text += f"<b>Service Time:</b> {st.session_state.total_service} minutes"
            elements.append(Paragraph(summary_text, styles['Normal']))
            elements.append(Spacer(1, 12))
            
            # Route table
            elements.append(Paragraph("Route Details", styles['Heading2']))
            route_data = [['Stop #', 'Location', 'Arrival', 'Service', 'Time']]
            for _, row in st.session_state.route_df.iterrows():
                route_data.append([
                    str(row['Stop #']),
                    row['Location'][:40] + '...' if len(row['Location']) > 40 else row['Location'],
                    row['Arrival'],
                    row['Service Time'],
                    row['Time from Start']
                ])
            
            route_table = Table(route_data)
            route_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(route_table)
            
            # Unassigned locations
            if not st.session_state.unassigned_df.empty:
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Unassigned Locations", styles['Heading2']))
                unassigned_data = [['Address', 'Window Start', 'Window End', 'Reason']]
                for _, row in st.session_state.unassigned_df.iterrows():
                    unassigned_data.append([
                        row['Address'][:40] + '...' if len(row['Address']) > 40 else row['Address'],
                        row['Window Start'],
                        row['Window End'],
                        row['Reason']
                    ])
                
                unassigned_table = Table(unassigned_data)
                unassigned_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(unassigned_table)
            
            doc.build(elements)
            pdf_data = pdf_buffer.getvalue()
            
            st.download_button(
                "📑 Download PDF",
                pdf_data,
                f"optimized_route_{st.session_state.optimization_date.strftime('%Y%m%d')}.pdf",
                "application/pdf",
                key="pdf_download"
            )
        else:
            st.button("📑 PDF (Install reportlab)", disabled=True, key="pdf_disabled")

###############################################################################
# end of route_optimizer_v2.py
############################################################################### 