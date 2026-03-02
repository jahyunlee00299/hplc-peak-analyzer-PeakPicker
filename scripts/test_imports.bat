@echo off
cd /d C:\Users\Jahyun\PycharmProjects\PeakPicker
echo Testing with base env...
C:\Users\Jahyun\anaconda3\python.exe -u -c "import sys; print('py ok'); import numpy; print('numpy ok'); import matplotlib; matplotlib.use('Agg'); print('mpl ok')" > test_out.txt 2> test_err.txt
echo Base Exit: %errorlevel%
type test_out.txt
echo --ERR--
type test_err.txt
