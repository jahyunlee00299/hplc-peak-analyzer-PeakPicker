@echo off
cd /d C:\Users\Jahyun\PycharmProjects\PeakPicker
C:\Users\Jahyun\anaconda3\envs\peakpicker\python.exe -m py_compile analyze_260225_massbalance.py > test_out.txt 2> test_err.txt
echo Compile exit: %errorlevel%
type test_out.txt
type test_err.txt
