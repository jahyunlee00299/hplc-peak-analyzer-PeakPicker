"""
PeakPicker - Chromatography Data Analysis Tool
Main Streamlit Application
"""

import streamlit as st
import sys
import os
from pathlib import Path

# Add modules to path
sys.path.append(str(Path(__file__).parent))

from modules.data_loader import DataLoader
from modules.visualizer import ChromatogramVisualizer


def main():
    """Main application"""

    # Page configuration
    st.set_page_config(
        page_title="PeakPicker",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Title
    st.title("📊 PeakPicker - Chromatography Data Analysis")
    st.markdown("**Feature 1**: Data Loading & Chromatogram Visualization")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # File uploader
        st.subheader("1. Load Data File")
        uploaded_file = st.file_uploader(
            "Choose a chromatography data file",
            type=['csv', 'txt', 'xlsx', 'xls'],
            help="Supported formats: CSV, TXT, Excel, ChemStation .ch (coming soon)"
        )

        # Visualization settings
        st.subheader("2. Visualization Settings")
        plot_color = st.color_picker("Line Color", "#0000FF")
        line_width = st.slider("Line Width", 0.5, 3.0, 1.0, 0.1)
        show_grid = st.checkbox("Show Grid", value=True)

        # Time range filter
        st.subheader("3. Time Range Filter")
        enable_filter = st.checkbox("Enable Time Filter", value=False)

    # Main content area
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

            st.success(f"✅ Data loaded successfully: {uploaded_file.name}")

            # Display data info
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
                    title=f"Chromatogram - {uploaded_file.name} (Zoomed)"
                )
            else:
                fig = visualizer.plot_chromatogram(
                    time, intensity,
                    title=f"Chromatogram - {uploaded_file.name}",
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
                    file_name=f"{uploaded_file.name}_processed.csv",
                    mime="text/csv"
                )

        except Exception as e:
            st.error(f"❌ Error loading data: {str(e)}")
            st.exception(e)

    else:
        # Welcome screen
        st.info("👈 Upload a chromatography data file to get started")

        st.markdown("""
        ## Welcome to PeakPicker!

        ### Supported File Formats:
        - **CSV/TXT**: Two columns (Time, Intensity)
        - **Excel**: First sheet with Time and Intensity columns
        - **ChemStation .ch**: Coming in next feature

        ### Current Features (v0.1):
        - ✅ Load chromatography data from multiple formats
        - ✅ Interactive chromatogram visualization
        - ✅ Time range filtering
        - ✅ Customizable plot appearance
        - ✅ Raw data table view
        - ✅ Export processed data

        ### Coming Soon:
        - Peak detection and integration
        - Baseline correction
        - Peak splitting
        - Quantitative analysis
        - Standard curve calibration
        - Excel report generation
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
