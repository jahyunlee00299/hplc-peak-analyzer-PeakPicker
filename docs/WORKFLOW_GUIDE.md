# Fully Automated Workflow Guide

## Overview

`complete_workflow.py` automates the entire HPLC data analysis process:

```
Export (Chemstation) → Baseline Correction → Peak Detection → Quantification → Visualization
```

## Quick Start

### Method 1: Start from Export

Extract data directly from Chemstation and analyze it.

```bash
python complete_workflow.py
```

1. Enter `1` at the mode selection (start from Export)
2. Confirm that Chemstation is running, then press Enter
3. Choose a folder browsing mode (interactive / direct path / full scan)
4. Analysis and visualization complete automatically

### Method 2: Analyze an Existing Folder

If you already have exported CSV files:

```bash
python complete_workflow.py
```

1. Enter `2` at the mode selection (analyze an existing folder)
2. Enter the folder path: `result/DEF_LC 2025-05-19 17-57-25`
3. Analysis and visualization complete automatically

### Method 3: Programmatic Usage

Call directly from Python code:

```python
from complete_workflow import WorkflowManager
from pathlib import Path

workflow = WorkflowManager()
workflow.output_folder = Path("result/your_folder_name")

if workflow.run_quantification():
    workflow.show_results_viewer()
```

## Visualization Window Features

Once analysis is complete, an interactive result viewer is displayed:

### Tab 1: Calibration Curve

- Peak area vs. concentration graph
- Linear regression line (measured vs. reference values)
- R² value and regression equation
- Distribution of replicate measurements

### Tab 2: Summary by Concentration

- Statistics per concentration (mean, standard deviation, sample count)
- RT, height, area information
- A table organized in CSV format

### Tab 3: Full Detail Data

- Detailed information for every peak
- Sample name, concentration, RT, height, area, width, etc.
- Up to 500 rows displayed

### Bottom Buttons

- **Open Folder**: open the folder containing the results in Explorer
- **Close**: close the visualization window

## Output Results

Analysis results are saved to `result/{folder_name}/quantification/`:

```
quantification/
├── calibration_curve.png       # calibration curve graph
├── peak_area_summary.csv       # summary statistics by concentration
└── all_peaks_detailed.csv      # full peak detail information
```

## Analysis Parameters

### Area Calculation Method

- **Boundary detection**: point where the signal returns to baseline (noise_level * 2)
- **Integration method**: trapezoidal integration
- **Time unit**: seconds (minutes → seconds conversion)
- **Accuracy**: 97% (relative to reference values)

### Calibration Curve Comparison

Reference values (Chemstation or another standard):
- y0 (intercept): 2173.0209
- a (slope): 52004.0462

Measured values are automatically compared against the reference, and the difference is shown as a percentage.

## Troubleshooting

### Export Failure

- Check that Chemstation is running
- Check that the correct data folder is selected
- If keyboard automation timing needs adjusting, edit `auto_export_keyboard_final.py`

### Analysis Failure

- Check that the CSV file is in the correct format (UTF-16 LE, tab-separated)
- Check whether the folder path contains Korean characters
- If no peaks are detected, check the signal intensity

### Visualization Window Does Not Appear

- Check that Tkinter is installed
- Install the Pillow library: `pip install Pillow`
- Check the matplotlib version: `pip install --upgrade matplotlib`

## Advanced Usage

### Custom Parameters

Adjust parameters in the `PeakQuantifier` class in `quantify_peaks.py`:

```python
# Select the baseline method
baseline_method = 'robust_fit'  # or 'weighted_spline'

# Adjust peak detection sensitivity
min_prominence = signal_range * 0.005
min_height = noise_level * 2

# Baseline-return threshold
baseline_threshold = noise_level * 2
```

### Batch Analysis

Analyze multiple folders at once:

```python
from complete_workflow import WorkflowManager
from pathlib import Path

folders = [
    "result/Experiment1",
    "result/Experiment2",
    "result/Experiment3"
]

for folder in folders:
    workflow = WorkflowManager()
    workflow.output_folder = Path(folder)
    workflow.run_quantification()
    # only visualize the last one

# Visualize the final result
workflow.show_results_viewer()
```

## Notes

- The full process typically takes 1-2 minutes (depending on the number of samples)
- Closing the visualization window ends the program
- All CSV files generated during analysis can be opened in Excel
- Calibration curve images are saved in PNG format and can be inserted directly into reports
