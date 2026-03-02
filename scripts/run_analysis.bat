@echo off
cd /d C:\Users\Jahyun\PycharmProjects\PeakPicker
C:\Users\Jahyun\anaconda3\python.exe -u analyze_260225_massbalance.py > run_out.txt 2> run_err.txt
echo Exit: %errorlevel%
type run_out.txt
echo ---STDERR---
type run_err.txt
