#!/usr/bin/env python
"""
Quick Start Script for HPLC Peak Picker
Simple wizard-style interface for running analysis
"""

import sys
from pathlib import Path
from hplc_analyzer import HPLCAnalyzer


def print_header():
    print("=" * 60)
    print("HPLC Peak Picker - Quick Start")
    print("=" * 60)
    print()


def get_data_directory():
    """Get data directory from user"""
    print("Enter the path to your Chemstation DATA directory:")
    print("(Default: C:/Chem32/1/DATA)")
    print()

    data_dir = input("Path: ").strip()

    if not data_dir:
        data_dir = "C:/Chem32/1/DATA"

    data_path = Path(data_dir)

    if not data_path.exists():
        print(f"\nERROR: Directory not found: {data_dir}")
        print("Please check the path and try again.")
        return None

    return data_dir


def get_yes_no(prompt, default=True):
    """Get yes/no input from user"""
    default_text = "Y/n" if default else "y/N"
    response = input(f"{prompt} [{default_text}]: ").strip().lower()

    if not response:
        return default

    return response in ['y', 'yes']


def main():
    print_header()

    # Get data directory
    data_dir = get_data_directory()
    if not data_dir:
        input("\nPress Enter to exit...")
        return 1

    print(f"\n[OK] Using data directory: {data_dir}")
    print()

    # Ask about output directory
    use_custom_output = get_yes_no("Use custom output directory?", False)

    if use_custom_output:
        output_dir = input("Output directory: ").strip()
        if not output_dir:
            output_dir = None
    else:
        output_dir = None

    # Ask about plots
    create_plots = get_yes_no("Create chromatogram plots? (may be slow for many files)", False)

    # Ask about export format
    print("\nExport format:")
    print("1. Excel (recommended)")
    print("2. CSV")
    print("3. Both")
    format_choice = input("Choice [1]: ").strip()

    format_map = {'1': 'excel', '2': 'csv', '3': 'both', '': 'excel'}
    export_format = format_map.get(format_choice, 'excel')

    # Ask about target RTs
    use_target_rts = get_yes_no("Search for specific retention times?", False)
    target_rts = None

    if use_target_rts:
        print("\nEnter target retention times (space-separated, e.g., 2.5 5.8 10.2):")
        rt_input = input("RTs: ").strip()
        if rt_input:
            try:
                target_rts = [float(x) for x in rt_input.split()]
                print(f"[OK] Will search for RTs: {target_rts}")
            except ValueError:
                print("WARNING: Invalid input, skipping target RT search")
                target_rts = None

    # Confirmation
    print("\n" + "=" * 60)
    print("Analysis Configuration:")
    print(f"  Data directory: {data_dir}")
    print(f"  Output directory: {output_dir if output_dir else 'Auto (in data directory)'}")
    print(f"  Export format: {export_format}")
    print(f"  Create plots: {'Yes' if create_plots else 'No'}")
    if target_rts:
        print(f"  Target RTs: {target_rts}")
    print("=" * 60)
    print()

    if not get_yes_no("Proceed with analysis?", True):
        print("Analysis cancelled.")
        input("\nPress Enter to exit...")
        return 0

    # Run analysis
    print("\nStarting analysis...\n")

    try:
        analyzer = HPLCAnalyzer(
            data_directory=data_dir,
            output_directory=output_dir,
        )

        analyzer.analyze_batch(
            recursive=True,
            export_format=export_format,
            create_plots=create_plots,
        )

        if target_rts:
            print(f"\nSearching for target retention times: {target_rts}")
            analyzer.analyze_with_target_peaks(target_rts, tolerance=0.1)

        print("\n" + "=" * 60)
        print("[SUCCESS] Analysis completed successfully!")
        print("=" * 60)

        input("\nPress Enter to exit...")
        return 0

    except Exception as e:
        print(f"\n[ERROR] Analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        return 1


if __name__ == "__main__":
    sys.exit(main())
