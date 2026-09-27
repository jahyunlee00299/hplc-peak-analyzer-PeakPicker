# Output Directory Structure Guide

## Overview
Starting with v2.1, output files are systematically organized under the `result/` folder.

## Output Directory Options

### Option 1: Use the Suggested Path (default) ✅
Automatically creates a subfolder named after the selected data folder.

**Example:**
```
Data folder: C:\Chem32\1\DATA\ExperimentA\

Output structure:
PeakPicker/
  └── result/
      └── ExperimentA/           ← auto-created
          ├── Sample1.csv
          ├── Sample2.csv
          └── Sample3.csv
```

**Advantages:**
- Systematically separates data from multiple experiments
- Experiments distinguishable by folder name
- Automatically saved to the same folder on re-runs

---

### Option 2: Save Directly to the result/ Folder
Saves all CSV files directly into the `result/` folder.

**Example:**
```
PeakPicker/
  └── result/
      ├── Sample1.csv
      ├── Sample2.csv
      ├── Sample3.csv
      ├── Exp1_Sample1.csv
      └── Exp2_Sample1.csv
```

**Usage scenarios:**
- When processing only a small amount of data
- When subfolders are unnecessary

---

### Option 3: Custom Path
Directly specify the desired path.

**Example:**
```
Input: D:\HPLC_Results\2025-11-Experiment\

Output structure:
D:/HPLC_Results/
  └── 2025-11-Experiment/
      ├── Sample1.csv
      ├── Sample2.csv
      └── Sample3.csv
```

**Usage scenarios:**
- When you want to save to a specific project folder
- When you want to save to an external drive

---

## Execution Examples

### Example 1: Processing a Single Experiment Folder

```bash
python auto_export_keyboard_final.py

# Select the data folder
Selection: C:\Chem32\1\DATA\ExperimentA\

# Configure the output directory
Suggested path: result/ExperimentA/
Choice (1, 2, or 3, Enter=1): [Enter]

✅ Output directory created
→ result/ExperimentA/
```

**Result:**
```
PeakPicker/
  └── result/
      └── ExperimentA/
          ├── Sample1.csv
          ├── Sample2.csv
          └── Sample3.csv
```

---

### Example 2: Processing Multiple Experiment Folders Sequentially

**First run:**
```bash
python auto_export_keyboard_final.py

# Data: C:\Chem32\1\DATA\Experiment_A\
# Output: result/Experiment_A/
```

**Second run:**
```bash
python auto_export_keyboard_final.py

# Data: C:\Chem32\1\DATA\Experiment_B\
# Output: result/Experiment_B/
```

**Result:**
```
PeakPicker/
  └── result/
      ├── Experiment_A/
      │   ├── Sample1.csv
      │   └── Sample2.csv
      └── Experiment_B/
          ├── Sample1.csv
          └── Sample2.csv
```

---

### Example 3: Full Scan Mode (Option 3)

```bash
python auto_export_keyboard_final.py

# Select Option 3: full folder scan
Scan path: C:\Chem32\1\DATA\

Found 125 .D folders in total!

# Configure the output directory
Suggested path: result/DATA/
Choice: 1

→ All CSV files saved to result/DATA/
```

**Result:**
```
PeakPicker/
  └── result/
      └── DATA/
          ├── Experiment_A_Sample1.csv
          ├── Experiment_A_Sample2.csv
          ├── Experiment_B_Sample1.csv
          └── ... (125 files)
```

---

## Folder Naming Rules

### Auto-Generated Subfolder Name

The **last folder name** of the selected data folder is used:

| Data folder path | Generated subfolder |
|------------------|-------------------|
| `C:\Chem32\1\DATA\ExperimentA\` | `result/ExperimentA/` |
| `C:\Chem32\1\DATA\2. ExperimentB cascade HPLC\` | `result/2. ExperimentB cascade HPLC/` |
| `C:\Chem32\1\DATA\` | `result/DATA/` |
| `D:\Experiments\2025-11-06\` | `result/2025-11-06/` |

---

## File Overwriting

If a file already exists at the same path:
- ✅ **Automatically skipped** (file already exists)
- Shown as `[Skipped]` in the progress output

**Example:**
```
[1/10] Skipped: Sample1 (already exists)
[2/10] Sample2
  Processing: Sample2.D
  [Success] 45,231 bytes
```

---

## Recommended Workflow

### Separate Saving Per Experiment (recommended) ⭐
```bash
# Run separately for each experiment
1. ExperimentA experiment → result/ExperimentA/
2. ExperimentB experiment → result/ExperimentB/
3. Control experiment → result/Control/
```

### Separate Saving by Date
```bash
# Include the date in the folder name
1. DATA/2025-11-06_Exp1/ → result/2025-11-06_Exp1/
2. DATA/2025-11-07_Exp2/ → result/2025-11-07_Exp2/
```

### Custom Path Per Project
```bash
# Use Option 3
1. Project_A → D:/Projects/ProjectA/HPLC_Data/
2. Project_B → D:/Projects/ProjectB/HPLC_Data/
```

---

## Linking with the Analysis Step

Automatically run analysis after export:

```bash
# 1. Export
python auto_export_keyboard_final.py
# → CSV saved to result/ExperimentA/

# 2. Analyze
python hplc_analyzer_enhanced.py "result/ExperimentA"
# → Excel saved to result/ExperimentA/analysis_results/
```

**Final structure:**
```
PeakPicker/
  └── result/
      └── ExperimentA/
          ├── Sample1.csv
          ├── Sample2.csv
          └── analysis_results/
              ├── Sample1_peaks.xlsx
              └── Sample2_peaks.xlsx
```

---

## Summary

| Option | Path | Usage scenario |
|------|------|--------------|
| **1** | `result/{folder_name}/` | ⭐ default, separated per experiment |
| **2** | `result/` | simple structure, small amounts of data |
| **3** | user-specified | specific project path |

**Default recommendation:** use Option 1 (Enter)
