@echo off
title RealTime Vibration Server - Telegram Bot
color 0A

echo.
echo ========================================
echo    REAL-TIME VIBRATION ANALYSIS
echo    TELEGRAM BOT SERVER
echo ========================================
echo.

echo [INFO] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan! Pastikan Python sudah terinstall.
    echo [INFO] Download Python dari: https://python.org
    pause
    exit /b 1
)

echo [INFO] Python ditemukan!
echo.

echo [INFO] Menuju ke direktori server...
cd /d "C:\Users\ASUS\Dropbox\My PC (LAPTOP-TPQANILH)\Downloads\RealTime_TA"

if not exist "realtime_vibration_server_telegram_fixed.py" (
    echo [ERROR] File server tidak ditemukan!
    echo [INFO] Pastikan file realtime_vibration_server_telegram_fixed.py ada di folder ini.
    pause
    exit /b 1
)

echo [INFO] Direktori server ditemukan!
echo.

echo [INFO] Memeriksa dependencies...
python -c "import flask, telegram, pandas, numpy, sklearn" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Beberapa dependencies mungkin belum terinstall.
    echo [INFO] Menjalankan server anyway...
    echo.
)

echo ========================================
echo    STARTING SERVER...
echo ========================================
echo.
echo [INFO] Server akan berjalan di: http://localhost:5000
echo [INFO] Telegram Bot akan aktif dalam beberapa detik...
echo [INFO] Gunakan CTRL+C untuk menghentikan server
echo.
echo ========================================
echo.

python realtime_vibration_server_telegram_fixed.py

echo.
echo ========================================
echo    SERVER STOPPED
echo ========================================
echo.
echo [INFO] Server telah dihentikan.
echo [INFO] Tekan tombol apapun untuk keluar...
pause >nul 