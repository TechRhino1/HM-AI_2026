@echo off
if exist "C:\Users\musu9\AppData\Local\Python\pythoncore-3.14-64\python.exe" (
    "C:\Users\musu9\AppData\Local\Python\pythoncore-3.14-64\python.exe" "%~dp0jarvis.py" %*
) else (
    python "%~dp0jarvis.py" %*
)
