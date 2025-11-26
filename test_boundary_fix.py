"""Test improved peak boundary calculation on problematic sample"""
import sys
import numpy as np
import pandas as pd

# Import the enhanced analyzer
from hplc_analyzer_enhanced import EnhancedHPLCAnalyzer

def main():
    # Load the problematic sample data from Excel
    sample_name = '251111_RIBA_PH_MAIN_6H_TH9_2'
    excel_path = f'result/자현_riba_ph/exported/{sample_name}_peaks.xlsx'

    print('='*80)
    print('TESTING IMPROVED PEAK BOUNDARY CALCULATION')
    print('='*80)
    print(f'Sample: {sample_name}')
    print()

    # Load BEFORE data (from existing export)
    print('=== BEFORE (Original Method) ===')
    df_before = pd.read_excel(excel_path, sheet_name='Peaks')
    peak_5_before = df_before[df_before['peak_number'] == 5].iloc[0]

    print(f"Peak 5:")
    print(f"  Retention Time: {peak_5_before['retention_time']:.2f} min")
    print(f"  Height: {peak_5_before['height']:.2f}")
    print(f"  Area: {peak_5_before['area']:.2f}")
    print(f"  Start Time: {peak_5_before['start_time']:.2f} min")
    print(f"  End Time: {peak_5_before['end_time']:.2f} min")
    print(f"  Duration: {peak_5_before['end_time'] - peak_5_before['start_time']:.2f} min")
    print(f"  Area/Height: {peak_5_before['area'] / peak_5_before['height']:.2f}")
    print()

    # Now load and analyze with NEW method
    print('=== AFTER (Improved Method) ===')

    # Load raw CSV data
    csv_path = f'result/자현_riba_ph/csv/{sample_name}.csv'

    # Parse CSV (handle binary format)
    try:
        # Try UTF-16 encoding first (Chemstation export format)
        with open(csv_path, 'rb') as f:
            # Read as binary and decode
            content = f.read()
            try:
                text = content.decode('utf-16')
            except:
                text = content.decode('utf-16-le')

        # Parse the text
        lines = text.split('\n')

        # Find data start
        data_start = 0
        for i, line in enumerate(lines):
            if 'Time' in line or 'min' in line or line.strip().replace('\t', '').replace(',', '').replace('.', '').replace('-', '').isdigit():
                data_start = i
                break

        # Extract time and intensity
        time_data = []
        intensity_data = []

        for line in lines[data_start:]:
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    t = float(parts[0].replace(',', '.'))
                    val = float(parts[1].replace(',', '.'))
                    time_data.append(t)
                    intensity_data.append(val)
                except:
                    continue

        time = np.array(time_data)
        intensity = np.array(intensity_data)

        print(f"Loaded {len(time)} data points")
        print(f"Time range: {time.min():.2f} - {time.max():.2f} min")
        print()

        # Analyze with improved method
        analyzer = EnhancedHPLCAnalyzer(
            data_directory='result/자현_riba_ph',
            enable_deconvolution=False  # Just test peak detection
        )
        result = analyzer.analyze_sample(time, intensity)

        if result and result.peak_data:
            print(f"Found {len(result.peak_data)} peaks")
            print()

            # Find peak 5
            peak_5_after = None
            for peak in result.peak_data:
                if peak['peak_number'] == 5:
                    peak_5_after = peak
                    break

            if peak_5_after:
                print(f"Peak 5:")
                print(f"  Retention Time: {peak_5_after['retention_time']:.2f} min")
                print(f"  Height: {peak_5_after['height']:.2f}")
                print(f"  Area: {peak_5_after['area']:.2f}")
                print(f"  Start Time: {peak_5_after['start_time']:.2f} min")
                print(f"  End Time: {peak_5_after['end_time']:.2f} min")
                print(f"  Duration: {peak_5_after['end_time'] - peak_5_after['start_time']:.2f} min")
                print(f"  Area/Height: {peak_5_after['area'] / peak_5_after['height']:.2f}")
                print()

                # Compare
                print('='*80)
                print('COMPARISON')
                print('='*80)
                print(f"Duration:      {peak_5_before['end_time'] - peak_5_before['start_time']:.2f} min → {peak_5_after['end_time'] - peak_5_after['start_time']:.2f} min")
                print(f"Area:          {peak_5_before['area']:.2f} → {peak_5_after['area']:.2f}")
                print(f"Area/Height:   {peak_5_before['area'] / peak_5_before['height']:.2f} → {peak_5_after['area'] / peak_5_after['height']:.2f}")

                improvement = (1 - (peak_5_after['area'] / peak_5_before['area'])) * 100
                print(f"\nArea reduced by: {improvement:.1f}%")

                duration_improvement = (1 - ((peak_5_after['end_time'] - peak_5_after['start_time']) / (peak_5_before['end_time'] - peak_5_before['start_time']))) * 100
                print(f"Duration reduced by: {duration_improvement:.1f}%")

                if peak_5_after['end_time'] - peak_5_after['start_time'] < 2.0:
                    print("\n✓ SUCCESS: Peak duration is now reasonable (<2 min)")
                else:
                    print("\n⚠ Peak duration still too wide")
            else:
                print("ERROR: Peak 5 not found in new analysis!")
        else:
            print("ERROR: Analysis failed!")

    except Exception as e:
        print(f"ERROR loading CSV: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
