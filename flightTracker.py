import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io

# Configure the page
st.set_page_config(
    page_title="FAA Part 117 Visual FDP Tracker",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for enhanced styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
        background: linear-gradient(90deg, #1f77b4, #2ecc71);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: bold;
    }
    .aircraft-card {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-left: 5px solid #3498db;
    }
    .critical-card {
        border-left: 5px solid #e74c3c;
        background: linear-gradient(135deg, #ffebee, #ffffff);
    }
    .warning-card {
        border-left: 5px solid #f39c12;
        background: linear-gradient(135deg, #fff3e0, #ffffff);
    }
    .crew-bar {
        margin: 0.5rem 0;
        padding: 0.5rem;
        border-radius: 5px;
    }
    .ca-bar { background-color: #e3f2fd; }
    .fo-bar { background-color: #e8f5e8; }
    .cabin-bar { background-color: #fff3e0; }
    .progress-container {
        background: #ecf0f1;
        border-radius: 10px;
        height: 25px;
        margin: 0.2rem 0;
        position: relative;
        overflow: hidden;
    }
    .progress-fill {
        height: 100%;
        border-radius: 10px;
        transition: width 0.5s ease-in-out;
        position: relative;
    }
    .progress-text {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        font-weight: bold;
        font-size: 0.8rem;
        color: #2c3e50;
        text-shadow: 1px 1px 2px white;
    }
    .tail-number {
        font-size: 1.2rem;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 0.5rem;
    }
    .crew-label {
        font-size: 0.9rem;
        font-weight: bold;
        margin-bottom: 0.2rem;
    }
</style>
""", unsafe_allow_html=True)

def hhmm_to_minutes(hhmm):
    """Convert HHMM format to total minutes"""
    if pd.isna(hhmm) or hhmm == '' or hhmm is None:
        return 0
    try:
        hhmm_str = str(int(float(hhmm))).zfill(4)
        hours = int(hhmm_str[:2])
        minutes = int(hhmm_str[2:])
        if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
            return 0
        return hours * 60 + minutes
    except (ValueError, TypeError):
        return 0

def minutes_to_hhmm(total_minutes):
    """Convert minutes to HHMM format"""
    if total_minutes <= 0:
        return "0000"
    total_minutes = int(total_minutes)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    hours = hours % 24 if hours >= 24 else hours
    return f"{hours:02d}{minutes:02d}"

def calculate_fdp_limits(start_time_hhmm, segments=1):
    """Calculate FDP limits based on start time and segments per FAA Part 117"""
    try:
        hours = int(str(start_time_hhmm).zfill(4)[:2])
        if 500 <= hours <= 759:
            return 14 if segments <= 2 else 13
        elif 800 <= hours <= 1259:
            return 13 if segments <= 2 else 12
        elif 1300 <= hours <= 1659:
            return 12 if segments <= 2 else 11
        else:
            return 11 if segments <= 2 else 10
    except:
        return 9

def calculate_progress_data(row, crew_type):
    """Calculate progress bar data for each crew type"""
    try:
        if crew_type == 'CA':
            max_time = row['CA Max FDP (hours)']
            elapsed = row['CA Elapsed FDP (HHMM)']
        elif crew_type == 'FO':
            max_time = row['FO Max FDP (hours)']
            elapsed = row['FO Elapsed FDP (HHMM)']
        else:  # Cabin
            max_time = row['Cabin Max FDP (hours)']
            elapsed = row['Cabin Elapsed FDP (HHMM)']
        
        max_minutes = max_time * 60
        elapsed_minutes = hhmm_to_minutes(elapsed)
        
        remaining_minutes = max(0, max_minutes - elapsed_minutes)
        progress_percent = min(100, (elapsed_minutes / max_minutes) * 100) if max_minutes > 0 else 0
        
        # Determine color based on remaining time
        if remaining_minutes <= 60:  # 1 hour or less
            color = "#e74c3c"  # Red
            status = "critical"
        elif remaining_minutes <= 120:  # 2 hours or less
            color = "#f39c12"  # Orange
            status = "warning"
        else:
            color = "#2ecc71"  # Green
            status = "ok"
        
        return {
            'progress_percent': progress_percent,
            'remaining_hhmm': minutes_to_hhmm(remaining_minutes),
            'elapsed_hhmm': elapsed,
            'max_hhmm': minutes_to_hhmm(max_minutes),
            'color': color,
            'status': status
        }
    except Exception as e:
        return {
            'progress_percent': 0,
            'remaining_hhmm': "0000",
            'elapsed_hhmm': "0000",
            'max_hhmm': "0000",
            'color': "#95a5a6",
            'status': 'error'
        }

def create_progress_bar(progress_data, crew_type, label):
    """Create a visual progress bar for a crew member"""
    crew_labels = {
        'CA': {'name': 'Captain', 'emoji': '👨‍✈️', 'class': 'ca-bar'},
        'FO': {'name': 'First Officer', 'emoji': '👩‍✈️', 'class': 'fo-bar'},
        'Cabin': {'name': 'Cabin Crew', 'emoji': '👨‍💼', 'class': 'cabin-bar'}
    }
    
    crew_info = crew_labels.get(crew_type, {'name': crew_type, 'emoji': '👤', 'class': ''})
    
    return f"""
    <div class="crew-bar {crew_info['class']}">
        <div class="crew-label">
            {crew_info['emoji']} {crew_info['name']} - {label}
        </div>
        <div class="progress-container">
            <div class="progress-fill" style="width: {progress_data['progress_percent']}%; background-color: {progress_data['color']};">
                <div class="progress-text">
                    {progress_data['elapsed_hhmm']} / {progress_data['max_hhmm']} (Remaining: {progress_data['remaining_hhmm']})
                </div>
            </div>
        </div>
    </div>
    """

def create_aircraft_card(tail_number, aircraft_data):
    """Create a visual card for an aircraft with progress bars"""
    # Calculate overall status
    statuses = [data['status'] for data in aircraft_data.values()]
    if 'critical' in statuses:
        card_class = 'critical-card'
        status_emoji = '🚨'
    elif 'warning' in statuses:
        card_class = 'warning-card'
        status_emoji = '⚠️'
    else:
        card_class = 'aircraft-card'
        status_emoji = '✅'
    
    # Create progress bars HTML
    progress_bars = ""
    for crew_type, progress_data in aircraft_data.items():
        progress_bars += create_progress_bar(progress_data, crew_type, progress_data['remaining_hhmm'])
    
    return f"""
    <div class="{card_class}">
        <div class="tail-number">
            {status_emoji} {tail_number} - {aircraft_data['CA']['remaining_hhmm']} remaining
        </div>
        {progress_bars}
    </div>
    """

def initialize_aircraft_data():
    """Initialize sample aircraft data"""
    if 'aircraft_data' not in st.session_state:
        st.session_state.aircraft_data = pd.DataFrame([
            {
                'Tail Number': 'N123AA',
                'CA Check-in': '0800',
                'CA Max FDP (hours)': 13.0,
                'CA Elapsed FDP (HHMM)': '0430',
                'FO Check-in': '0800',
                'FO Max FDP (hours)': 13.0,
                'FO Elapsed FDP (HHMM)': '0430',
                'Cabin Check-in': '0730',
                'Cabin Max FDP (hours)': 14.0,
                'Cabin Elapsed FDP (HHMM)': '0500'
            },
            {
                'Tail Number': 'N456BB',
                'CA Check-in': '0600',
                'CA Max FDP (hours)': 14.0,
                'CA Elapsed FDP (HHMM)': '0830',
                'FO Check-in': '0600',
                'FO Max FDP (hours)': 14.0,
                'FO Elapsed FDP (HHMM)': '0830',
                'Cabin Check-in': '0530',
                'Cabin Max FDP (hours)': 14.0,
                'Cabin Elapsed FDP (HHMM)': '0900'
            },
            {
                'Tail Number': 'N789CC',
                'CA Check-in': '1200',
                'CA Max FDP (hours)': 12.0,
                'CA Elapsed FDP (HHMM)': '0230',
                'FO Check-in': '1200',
                'FO Max FDP (hours)': 12.0,
                'FO Elapsed FDP (HHMM)': '0230',
                'Cabin Check-in': '1130',
                'Cabin Max FDP (hours)': 13.0,
                'Cabin Elapsed FDP (HHMM)': '0300'
            }
        ])

def main():
    # Header
    st.markdown('<div class="main-header">✈️ FAA Part 117 Visual FDP Tracker</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Initialize data
    initialize_aircraft_data()
    
    # Sidebar for controls
    with st.sidebar:
        st.header("🎮 Controls")
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("🔄 Live Auto-Refresh", value=True)
        refresh_rate = st.slider("Refresh Rate (seconds)", 5, 60, 10)
        
        # Manual refresh
        if st.button("🔄 Manual Refresh Now", use_container_width=True):
            st.rerun()
        
        st.markdown("---")
        st.header("📊 Add New Aircraft")
        
        with st.form("new_aircraft"):
            tail_number = st.text_input("Tail Number", placeholder="N123AA")
            
            col1, col2 = st.columns(2)
            with col1:
                ca_checkin = st.text_input("CA Check-in", value="0800")
                fo_checkin = st.text_input("FO Check-in", value="0800")
                cabin_checkin = st.text_input("Cabin Check-in", value="0730")
            
            with col2:
                ca_elapsed = st.text_input("CA Elapsed", value="0000")
                fo_elapsed = st.text_input("FO Elapsed", value="0000")
                cabin_elapsed = st.text_input("Cabin Elapsed", value="0000")
            
            if st.form_submit_button("➕ Add Aircraft", use_container_width=True):
                if tail_number:
                    new_aircraft = {
                        'Tail Number': tail_number,
                        'CA Check-in': ca_checkin,
                        'CA Max FDP (hours)': calculate_fdp_limits(ca_checkin, 2),
                        'CA Elapsed FDP (HHMM)': ca_elapsed,
                        'FO Check-in': fo_checkin,
                        'FO Max FDP (hours)': calculate_fdp_limits(fo_checkin, 2),
                        'FO Elapsed FDP (HHMM)': fo_elapsed,
                        'Cabin Check-in': cabin_checkin,
                        'Cabin Max FDP (hours)': calculate_fdp_limits(cabin_checkin, 2),
                        'Cabin Elapsed FDP (HHMM)': cabin_elapsed
                    }
                    st.session_state.aircraft_data = pd.concat([
                        st.session_state.aircraft_data,
                        pd.DataFrame([new_aircraft])
                    ], ignore_index=True)
                    st.success(f"Added {tail_number} to tracking!")
        
        st.markdown("---")
        st.header("📈 Statistics")
        
        if not st.session_state.aircraft_data.empty:
            total_aircraft = len(st.session_state.aircraft_data)
            critical_count = 0
            warning_count = 0
            
            for _, aircraft in st.session_state.aircraft_data.iterrows():
                ca_data = calculate_progress_data(aircraft, 'CA')
                fo_data = calculate_progress_data(aircraft, 'FO')
                cabin_data = calculate_progress_data(aircraft, 'Cabin')
                
                if any(data['status'] == 'critical' for data in [ca_data, fo_data, cabin_data]):
                    critical_count += 1
                elif any(data['status'] == 'warning' for data in [ca_data, fo_data, cabin_data]):
                    warning_count += 1
            
            st.metric("Total Aircraft", total_aircraft)
            st.metric("Critical Alerts", critical_count, delta_color="inverse")
            st.metric("Warnings", warning_count)
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🛩️ Aircraft Status Dashboard")
        
        if not st.session_state.aircraft_data.empty:
            # Create visual cards for each aircraft
            for _, aircraft in st.session_state.aircraft_data.iterrows():
                tail_number = aircraft['Tail Number']
                
                # Calculate progress data for each crew type
                ca_data = calculate_progress_data(aircraft, 'CA')
                fo_data = calculate_progress_data(aircraft, 'FO')
                cabin_data = calculate_progress_data(aircraft, 'Cabin')
                
                aircraft_progress = {
                    'CA': ca_data,
                    'FO': fo_data,
                    'Cabin': cabin_data
                }
                
                # Create and display the aircraft card
                card_html = create_aircraft_card(tail_number, aircraft_progress)
                st.markdown(card_html, unsafe_allow_html=True)
        
        else:
            st.info("✈️ No aircraft being tracked. Use the sidebar to add aircraft.")
    
    with col2:
        st.header("🚨 Alert Summary")
        
        if not st.session_state.aircraft_data.empty:
            critical_aircraft = []
            warning_aircraft = []
            
            for _, aircraft in st.session_state.aircraft_data.iterrows():
                tail_number = aircraft['Tail Number']
                ca_data = calculate_progress_data(aircraft, 'CA')
                fo_data = calculate_progress_data(aircraft, 'FO')
                cabin_data = calculate_progress_data(aircraft, 'Cabin')
                
                if any(data['status'] == 'critical' for data in [ca_data, fo_data, cabin_data]):
                    critical_aircraft.append(tail_number)
                elif any(data['status'] == 'warning' for data in [ca_data, fo_data, cabin_data]):
                    warning_aircraft.append(tail_number)
            
            if critical_aircraft:
                st.error("### 🚨 CRITICAL ALERTS")
                for aircraft in critical_aircraft:
                    st.write(f"• {aircraft} - Immediate action required")
            
            if warning_aircraft:
                st.warning("### ⚠️ WARNINGS")
                for aircraft in warning_aircraft:
                    st.write(f"• {aircraft} - Monitor closely")
            
            if not critical_aircraft and not warning_aircraft:
                st.success("### ✅ ALL SYSTEMS NORMAL")
                st.write("All aircraft within safe limits")
        
        st.markdown("---")
        st.header("🕒 Last Updated")
        st.write(f"**{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")
        
        # Simulate time progression for demo
        if st.button("⏩ Simulate +30min", use_container_width=True):
            for idx, aircraft in st.session_state.aircraft_data.iterrows():
                # Add 30 minutes to elapsed times
                for col in ['CA Elapsed FDP (HHMM)', 'FO Elapsed FDP (HHMM)', 'Cabin Elapsed FDP (HHMM)']:
                    current = aircraft[col]
                    if current != '0000':
                        current_minutes = hhmm_to_minutes(current)
                        new_minutes = current_minutes + 30
                        st.session_state.aircraft_data.at[idx, col] = minutes_to_hhmm(new_minutes)
            st.rerun()
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(refresh_rate)
        st.rerun()

if __name__ == "__main__":
    main()