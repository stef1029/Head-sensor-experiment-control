@echo off
setlocal

set "PYTHON_EXE=C:\Users\Public\.conda\behaviour_analysis\python.exe"
set "SCRIPT_PATH=C:\Dev\projects\Head-sensor-experiment-control\debug\view_daq.py"

if "%~1"=="" (
    "%PYTHON_EXE%" "%SCRIPT_PATH%"
) else (
    "%PYTHON_EXE%" "%SCRIPT_PATH%" "%~1"
)

endlocal
