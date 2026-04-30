@echo off
REM Build Network Monitor as a standalone directory (--onedir, recommended)
REM Output: dist\NetworkMonitor\NetworkMonitor.exe

pip install -r requirements.txt

pyinstaller ^
  --name NetworkMonitor ^
  --onedir ^
  --noconsole ^
  --add-data "app\web\templates;app/web/templates" ^
  --add-data "app\web\static;app/web/static" ^
  --hidden-import win32timezone ^
  --hidden-import pkg_resources.py2_compat ^
  main.py

echo.
echo === Build termine ===
echo Executable : dist\NetworkMonitor\NetworkMonitor.exe
echo Lancer     : dist\NetworkMonitor\NetworkMonitor.exe
pause
