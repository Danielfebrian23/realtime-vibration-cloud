@echo off
echo Creating desktop shortcut for RealTime Vibration Server...

:: Get desktop path
for /f "tokens=2*" %%a in ('reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop 2^>nul') do set DESKTOP=%%b

:: Create shortcut
echo @echo off > "%DESKTOP%\Start RealTime Server.bat"
echo cd /d "C:\Users\ASUS\Dropbox\My PC (LAPTOP-TPQANILH)\Downloads\RealTime_TA" >> "%DESKTOP%\Start RealTime Server.bat"
echo start_server.bat >> "%DESKTOP%\Start RealTime Server.bat"

echo.
echo ========================================
echo    SHORTCUT BERHASIL DIBUAT!
echo ========================================
echo.
echo [INFO] Shortcut "Start RealTime Server.bat" telah dibuat di Desktop
echo [INFO] Double-click shortcut untuk menjalankan server
echo.
echo [INFO] Atau langsung jalankan: start_server.bat
echo.
pause 