# Project Structure

## Overview
PeakPicker is organized into a clean, systematic structure.

## Directory Structure

```
PeakPicker/
│
├── 📜 Main scripts
│   ├── auto_export_keyboard_final.py   # Automatic Chemstation export
│   └── hplc_analyzer_enhanced.py       # HPLC data analysis
│
├── 📚 docs/                            # Documentation folder
│   ├── USAGE_EXAMPLES.md               # Detailed usage guide
│   ├── OUTPUT_ORGANIZATION_GUIDE.md    # Output structure guide
│   └── TIMING_OPTIMIZATION_GUIDE.md    # Performance optimization guide
│
├── 🔧 src/                             # Source modules
│   ├── hybrid_baseline.py              # Baseline correction engine
│   ├── chemstation_parser.py           # Chemstation data parsing
│   └── result_exporter.py              # Excel result output
│
├── 💾 backup_scripts/                  # Backup/development scripts
│   └── (files from testing and development)
│
├── 📊 result/                          # Output results (auto-generated)
│   ├── Experiment1/
│   │   ├── Sample1.csv
│   │   ├── Sample2.csv
│   │   └── analysis_results/
│   │       ├── Sample1_peaks.xlsx
│   │       └── Sample2_peaks.xlsx
│   ├── Experiment2/
│   └── ...
│
├── 📄 README.md                        # Project overview
├── 📋 requirements.txt                 # Python package dependencies
└── 🚫 .gitignore                       # Git exclusion settings
```

## File Descriptions

### Main Scripts

#### `auto_export_keyboard_final.py`
- **Purpose**: automatically export .D folders from Chemstation → CSV
- **Run**: `python auto_export_keyboard_final.py`
- **Features**:
  - Interactive directory browsing (tree view)
  - Full folder scan mode
  - Recursive .D folder search
  - Keyboard automation (PyAutoGUI)

#### `hplc_analyzer_enhanced.py`
- **Purpose**: CSV file analysis and peak detection
- **Run**: `python hplc_analyzer_enhanced.py "path/to/csv"`
- **Features**:
  - Hybrid baseline correction
  - Adaptive peak detection
  - Excel result report generation

### Source Modules (src/)

#### `hybrid_baseline.py`
- Hybrid baseline combining Valley detection + Local Minimum
- 3 connection methods (weighted_spline, adaptive_connect, robust_fit)
- Robust performance across a 0.01x-10x scale range

#### `chemstation_parser.py`
- Chemstation CSV file parsing
- Data validation and preprocessing

#### `result_exporter.py`
- Excel report generation (openpyxl)
- Summary and Peak detail info sheets

### Documentation (docs/)

#### `USAGE_EXAMPLES.md`
- Usage guide
- Step-by-step execution instructions
- Troubleshooting tips

#### `OUTPUT_ORGANIZATION_GUIDE.md`
- Explanation of the output directory structure
- 3 output options
- How to organize folders per experiment

#### `TIMING_OPTIMIZATION_GUIDE.md`
- Keyboard automation timing optimization
- Per-step time settings
- Performance tuning guide

## Workflow

### Step 1: Export (Chemstation → CSV)
```bash
python auto_export_keyboard_final.py
```
- Select an option (interactive browsing / direct input / full scan)
- Set the output path (result/{folder_name}/)
- Run the automatic export

**Result**: `result/{folder_name}/*.csv`

### Step 2: Analyze (CSV → Excel)
```bash
python hplc_analyzer_enhanced.py "result/{folder_name}"
```
- Baseline correction
- Peak detection
- Excel report generation

**Result**: `result/{folder_name}/analysis_results/*_peaks.xlsx`

## Data Flow

```
Chemstation .D folder
    ↓
[auto_export_keyboard_final.py]
    ↓
result/{experiment_name}/Sample*.csv
    ↓
[hplc_analyzer_enhanced.py]
    ↓
result/{experiment_name}/analysis_results/Sample*_peaks.xlsx
```

## Folder Management

### Auto-Generated Folders
- `result/` - all output results
- `result/{experiment_name}/` - CSV files per experiment
- `result/{experiment_name}/analysis_results/` - analysis result Excel files

### Excluded Folders (.gitignore)
- `__pycache__/`
- `result/`
- `exported_signals/`
- `analysis_results/`
- `*.csv`, `*.xlsx` (result files)
- `*.png`, `*.jpg` (graphs)

### Backup Folder
- `backup_scripts/` - archive of development/test scripts

## Dependencies

### Python Packages
```bash
pip install numpy scipy pandas openpyxl pyautogui pyperclip
```

### System Requirements
- Python 3.8+
- Windows OS (Chemstation compatible)
- Chemstation installed (required for auto_export)

## Development History

### v2.1 (2025-11-06)
- ✅ Improved project structure (docs/, src/, result/)
- ✅ Full folder scan mode
- ✅ Interactive tree view
- ✅ Systematized output structure

### v2.0 (2025-11-06)
- ✅ Hybrid baseline
- ✅ Interactive path input
- ✅ Documentation added

## Related Documents

- [README.md](../README.md) - project overview
- [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) - detailed usage
- [OUTPUT_ORGANIZATION_GUIDE.md](OUTPUT_ORGANIZATION_GUIDE.md) - output structure
- [TIMING_OPTIMIZATION_GUIDE.md](TIMING_OPTIMIZATION_GUIDE.md) - performance optimization
