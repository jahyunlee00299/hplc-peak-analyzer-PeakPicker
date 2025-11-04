@echo off
REM HPLC Peak Picker - Quick Analysis Script
REM Edit the DATA_DIR variable below to point to your Chemstation data directory

echo ====================================
echo HPLC Peak Picker - Batch Analysis
echo ====================================
echo.

REM Set your data directory here
set DATA_DIR=C:\Chem32\1\DATA

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo Data directory: %DATA_DIR%
echo.
echo Starting analysis...
echo.

REM Run the analyzer with default settings
python hplc_analyzer.py "%DATA_DIR%" --format excel

if errorlevel 1 (
    echo.
    echo ERROR: Analysis failed
    pause
    exit /b 1
)

echo.
echo ====================================
echo Analysis Complete!
echo ====================================
echo.
echo Results have been saved to: %DATA_DIR%\analysis_results
echo.
pause
