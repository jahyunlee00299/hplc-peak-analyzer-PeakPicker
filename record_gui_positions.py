"""
Record mouse positions for Chemstation GUI automation
"""

import pyautogui
import time
import json

def record_positions():
    """Record exact mouse positions for automation"""

    print("="*80)
    print("Chemstation GUI Position Recorder")
    print("="*80)
    print("\nThis will record the exact mouse positions for automation.")
    print("After you see each prompt, move your mouse to that position and wait 3 seconds.")
    print("\nPress Enter to start...")
    input()

    positions = {}

    steps = [
        ("file_menu", "Move mouse to 'File' menu (top left)"),
        ("load_data", "Click 'File', then move to 'Load Data' or 'Open Data' menu item"),
        ("open_button", "In the file dialog, move to the 'Open' button"),
        ("file_menu_2", "After file is loaded, move to 'File' men"
                        ""
                        "u again"),
        ("export_menu", "With 'File' menu open, move to 'Export' menu item"),
        ("save_button", "In the export dialog, move to the 'Save' or 'Export' button"),
    ]

    for key, instruction in steps:
        print(f"\n{instruction}")
        print("Waiting 10 seconds...")
        time.sleep(10)

        pos = pyautogui.position()
        positions[key] = {"x": pos.x, "y": pos.y}
        print(f"  Recorded: {key} = ({pos.x}, {pos.y})")

    # Save positions to file
    with open("gui_positions.json", "w") as f:
        json.dump(positions, f, indent=2)

    print("\n" + "="*80)
    print("Positions saved to: gui_positions.json")
    print("="*80)

    print("\nRecorded positions:")
    for key, pos in positions.items():
        print(f"  {key}: ({pos['x']}, {pos['y']})")

    return positions

if __name__ == "__main__":
    record_positions()
