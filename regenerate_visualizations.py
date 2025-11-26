"""
Regenerate visualization plots for analyzed data
"""

import sys
from pathlib import Path

# Import the visualization function
sys.path.insert(0, str(Path(__file__).parent))
from run_complete_workflow import run_visualization

if __name__ == "__main__":
    data_dir = r"result\Revision 재실험"
    print(f"Regenerating visualizations for: {data_dir}")
    success = run_visualization(data_dir)

    if success:
        print("\n[OK] Visualization completed successfully!")
    else:
        print("\n[X] Visualization failed")
        sys.exit(1)
