"""
PeakPicker - Chromatography Data Analysis Tool
Main Streamlit Application with Session Management
"""

import streamlit as st
import sys
import os
from pathlib import Path
from datetime import datetime

# Add modules to path
sys.path.append(str(Path(__file__).parent))

from modules.data_loader import DataLoader
from modules.visualizer import ChromatogramVisualizer
from modules.session_manager import SessionManager


def initialize_session_state():
    """Initialize Streamlit session state"""
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'time' not in st.session_state:
        st.session_state.time = None
    if 'intensity' not in st.session_state:
        st.session_state.intensity = None
    if 'filename' not in st.session_state:
        st.session_state.filename = None
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None
    if 'session_manager' not in st.session_state:
        st.session_state.session_manager = SessionManager()


def save_current_session():
    """Save current session to file"""
    if not st.session_state.data_loaded:
        st.warning("No data loaded to save!")
        return False

    session_manager = st.session_state.session_manager

    # Create or use existing session
    if st.session_state.current_session_id is None:
        session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session_id = session_manager.create_session(session_name)
        st.session_state.current_session_id = session_id
    else:
        session_id = st.session_state.current_session_id

    # Prepare data to save
    data = {
        'filename': st.session_state.filename,
        'time': st.session_state.time,
        'intensity': st.session_state.intensity,
        'plot_settings': {
            'color': st.session_state.get('plot_color', '#0000FF'),
            'line_width': st.session_state.get('line_width', 1.0),
            'show_grid': st.session_state.get('show_grid', True),
        }
    }

    # Progress info
    progress = {
        'status': 'paused',
        'last_action': 'Data loaded and visualized',
        'timestamp': datetime.now().isoformat(),
    }

    # Save session
    success = session_manager.save_state(session_id, data, progress)

    if success:
        st.success(f"✅ Session saved: {session_id}")
        return True
    else:
        st.error("❌ Failed to save session")
        return False


def load_session(session_id):
    """Load session from file"""
    session_manager = st.session_state.session_manager

    session_data = session_manager.load_state(session_id)

    if session_data is None:
        st.error(f"❌ Session not found: {session_id}")
        return False

    # Load data from session
    data = session_data.get('data', {})

    st.session_state.time = data.get('time')
    st.session_state.intensity = data.get('intensity')
    st.session_state.filename = data.get('filename')
    st.session_state.data_loaded = True
    st.session_state.current_session_id = session_id

    # Load plot settings
    plot_settings = data.get('plot_settings', {})
    st.session_state.plot_color = plot_settings.get('color', '#0000FF')
    st.session_state.line_width = plot_settings.get('line_width', 1.0)
    st.session_state.show_grid = plot_settings.get('show_grid', True)

    st.success(f"✅ Session loaded: {session_id}")
    return True


def main():
    """Main application"""

    # Page configuration
    st.set_page_config(
        page_title="PeakPicker",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize session state
    initialize_session_state()

    # Title
    st.title("📊 PeakPicker - Chromatography Data Analysis")
    st.markdown("**Feature 1.5**: Data Loading, Visualization & Session Management")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # Session Management Section
        st.subheader("🔄 Session Management")

        # Current session info
        if st.session_state.current_session_id:
            st.info(f"**Current Session:**\n{st.session_state.current_session_id}")

        # Save session button
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Session", use_container_width=True):
                save_current_session()

        with col2:
            if st.button("🔄 New Session", use_container_width=True):
                st.session_state.current_session_id = None
                st.session_state.data_loaded = False
                st.session_state.time = None
                st.session_state.intensity = None
                st.session_state.filename = None
                st.success("New session started!")
                st.rerun()

        # Load existing sessions
        with st.expander("📂 Load Previous Session"):
            sessions = st.session_state.session_manager.list_sessions()

            if sessions:
                for session in sessions:
                    session_id = session['session_id']
                    status = session.get('status', 'unknown')
                    updated = session.get('updated_at', 'N/A')

                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.text(f"📌 {session_id}")
                        st.caption(f"Status: {status} | Updated: {updated[:19]}")
                    with col2:
                        if st.button("Load", key=f"load_{session_id}", use_container_width=True):
                            load_session(session_id)
                            st.rerun()

                    st.divider()
            else:
                st.info("No saved sessions found")

        st.divider()

        # File uploader
        st.subheader("1. Load Data File")
        uploaded_file = st.file_uploader(
            "Choose a chromatography data file",
            type=['csv', 'txt', 'xlsx', 'xls'],
            help="Supported formats: CSV, TXT, Excel, ChemStation .ch (coming soon)"
        )

        # Visualization settings
        st.subheader("2. Visualization Settings")
        plot_color = st.color_picker(
            "Line Color",
            st.session_state.get('plot_color', '#0000FF')
        )
        st.session_state.plot_color = plot_color

        line_width = st.slider(
            "Line Width",
            0.5, 3.0,
            st.session_state.get('line_width', 1.0),
            0.1
        )
        st.session_state.line_width = line_width

        show_grid = st.checkbox(
            "Show Grid",
            value=st.session_state.get('show_grid', True)
        )
        st.session_state.show_grid = show_grid

        # Time range filter
        st.subheader("3. Time Range Filter")
        enable_filter = st.checkbox("Enable Time Filter", value=False)

    # Main content area
    # Handle file upload
    if uploaded_file is not None:
        try:
            # Save uploaded file temporarily
            temp_path = Path("temp_data") / uploaded_file.name
            temp_path.parent.mkdir(exist_ok=True)

            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Load data
            with st.spinner("Loading data..."):
                loader = DataLoader()
                time, intensity = loader.load_file(str(temp_path))

            # Store in session state
            st.session_state.time = time
            st.session_state.intensity = intensity
            st.session_state.filename = uploaded_file.name
            st.session_state.data_loaded = True

            st.success(f"✅ Data loaded successfully: {uploaded_file.name}")

        except Exception as e:
            st.error(f"❌ Error loading data: {str(e)}")
            st.exception(e)

    # Display data if loaded (from upload or session)
    if st.session_state.data_loaded:
        time = st.session_state.time
        intensity = st.session_state.intensity
        filename = st.session_state.filename

        # Display data info
        loader = DataLoader()
        loader.time = time
        loader.intensity = intensity
        loader.file_path = filename
        data_info = loader.get_data_info()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Data Points", f"{data_info['data_points']:,}")
        with col2:
            st.metric(
                "Time Range",
                f"{data_info['time_range'][0]:.2f} - {data_info['time_range'][1]:.2f} min"
            )
        with col3:
            st.metric("Max Intensity", f"{data_info['intensity_range'][1]:.2f}")
        with col4:
            st.metric("Mean Intensity", f"{data_info['intensity_mean']:.2f}")

        # Time range filter controls
        time_range = None
        if enable_filter:
            st.subheader("Select Time Range")
            col1, col2 = st.columns(2)
            with col1:
                start_time = st.number_input(
                    "Start Time (min)",
                    min_value=float(data_info['time_range'][0]),
                    max_value=float(data_info['time_range'][1]),
                    value=float(data_info['time_range'][0]),
                    step=0.1
                )
            with col2:
                end_time = st.number_input(
                    "End Time (min)",
                    min_value=float(data_info['time_range'][0]),
                    max_value=float(data_info['time_range'][1]),
                    value=float(data_info['time_range'][1]),
                    step=0.1
                )
            time_range = (start_time, end_time)

        # Plot chromatogram
        st.subheader("Chromatogram")

        visualizer = ChromatogramVisualizer(figsize=(14, 6))

        if enable_filter and time_range:
            fig = visualizer.plot_interactive_region(
                time, intensity,
                time_range=time_range,
                title=f"Chromatogram - {filename} (Zoomed)"
            )
        else:
            fig = visualizer.plot_chromatogram(
                time, intensity,
                title=f"Chromatogram - {filename}",
                color=plot_color,
                linewidth=line_width,
                grid=show_grid
            )

        st.pyplot(fig)

        # Data table
        with st.expander("📋 View Raw Data"):
            import pandas as pd
            df = pd.DataFrame({
                'Time (min)': time,
                'Intensity': intensity
            })
            st.dataframe(df, height=300)

            # Download button
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download Data as CSV",
                data=csv,
                file_name=f"{filename}_processed.csv",
                mime="text/csv"
            )

    else:
        # Welcome screen
        st.info("👈 Upload a chromatography data file or load a saved session to get started")

        st.markdown("""
        ## Welcome to PeakPicker!

        ### 🆕 New Features (v0.2):
        - ✅ **Session Management**: Save and resume your work anytime
        - ✅ **Pause & Resume**: Interrupt your analysis and continue later
        - ✅ **Session History**: View and load previous sessions
        - ✅ **Auto-save Settings**: Your plot preferences are saved with sessions

        ### Supported File Formats:
        - **CSV/TXT**: Two columns (Time, Intensity)
        - **Excel**: First sheet with Time and Intensity columns
        - **ChemStation .ch**: Coming in next feature

        ### Current Features (v0.2):
        - ✅ Load chromatography data from multiple formats
        - ✅ Interactive chromatogram visualization
        - ✅ Time range filtering
        - ✅ Customizable plot appearance
        - ✅ Raw data table view
        - ✅ Export processed data
        - ✅ **Save and resume sessions**
        - ✅ **Session history management**

        ### Coming Soon:
        - Peak detection and integration
        - Baseline correction
        - Peak splitting
        - Quantitative analysis
        - Standard curve calibration
        - Excel report generation
        - **Batch processing with pause/resume**
        """)

        # Show example data format
        with st.expander("📄 Example CSV Format"):
            st.code("""
Time,Intensity
0.00,100.5
0.01,102.3
0.02,105.8
0.03,110.2
...
            """, language="csv")


if __name__ == "__main__":
    main()
