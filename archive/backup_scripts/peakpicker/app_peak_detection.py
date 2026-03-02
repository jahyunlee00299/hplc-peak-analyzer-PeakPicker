"""
Peak Detection section for app.py
This will be integrated into the main app
"""

import streamlit as st
import pandas as pd
from modules.peak_detector import PeakDetector

def peak_detection_section(time, intensity, filename):
    """Peak detection and integration section"""

    st.subheader("🔍 Peak Detection & Integration")

    with st.expander("⚙️ Peak Detection Parameters", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            auto_threshold = st.checkbox("Auto Threshold", value=True,
                                        help="Automatically calculate detection thresholds")

        with col2:
            if not auto_threshold:
                prominence = st.number_input("Prominence", value=100.0, min_value=0.0,
                                            help="Minimum peak prominence")
            else:
                prominence = None

        with col3:
            if not auto_threshold:
                min_height = st.number_input("Min Height", value=50.0, min_value=0.0,
                                            help="Minimum peak height")
            else:
                min_height = None

        col4, col5 = st.columns(2)
        with col4:
            min_width = st.number_input("Min Width (min)", value=0.01, min_value=0.001,
                                       step=0.005, format="%.3f",
                                       help="Minimum peak width in minutes")

        with col5:
            rel_height = st.slider("Rel Height", 0.1, 0.9, 0.5, 0.05,
                                  help="Relative height for width calculation (0.5=FWHM)")

    # Detect peaks button
    if st.button("🔍 Detect Peaks", type="primary", use_container_width=True):
        with st.spinner("Detecting peaks..."):
            # Create detector
            detector = PeakDetector(
                time, intensity,
                prominence=prominence,
                min_height=min_height,
                min_width=min_width,
                rel_height=rel_height,
                auto_threshold=auto_threshold
            )

            # Detect peaks
            peaks = detector.detect_peaks()

            # Store in session state
            st.session_state.peaks = peaks
            st.session_state.detector = detector

            if peaks:
                st.success(f"✅ Detected {len(peaks)} peaks!")
            else:
                st.warning("⚠️ No peaks detected. Try adjusting parameters.")

    # Display peaks if detected
    if 'peaks' in st.session_state and st.session_state.peaks:
        peaks = st.session_state.peaks

        # Summary metrics
        st.markdown("### 📊 Peak Summary")
        col1, col2, col3, col4 = st.columns(4)

        total_area = sum(p.area for p in peaks)
        avg_width = sum(p.width for p in peaks) / len(peaks)
        avg_height = sum(p.height for p in peaks) / len(peaks)

        with col1:
            st.metric("Total Peaks", len(peaks))
        with col2:
            st.metric("Total Area", f"{total_area:.2f}")
        with col3:
            st.metric("Avg Width", f"{avg_width:.3f} min")
        with col4:
            st.metric("Avg Height", f"{avg_height:.2f}")

        # Peak table
        st.markdown("### 📋 Peak Table")

        # Convert peaks to DataFrame
        peak_data = []
        for i, peak in enumerate(peaks, 1):
            peak_data.append({
                'Peak #': i,
                'RT (min)': f"{peak.rt:.3f}",
                'RT Start': f"{peak.rt_start:.3f}",
                'RT End': f"{peak.rt_end:.3f}",
                'Height': f"{peak.height:.2f}",
                'Area': f"{peak.area:.2f}",
                'Width (min)': f"{peak.width:.3f}",
                '% Area': f"{peak.percent_area:.2f}%"
            })

        df_peaks = pd.DataFrame(peak_data)
        st.dataframe(df_peaks, use_container_width=True, height=300)

        # Download button
        csv = df_peaks.to_csv(index=False)
        st.download_button(
            label="📥 Download Peak Table (CSV)",
            data=csv,
            file_name=f"{filename}_peaks.csv",
            mime="text/csv",
            use_container_width=True
        )
