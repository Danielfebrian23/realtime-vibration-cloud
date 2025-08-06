#!/usr/bin/env python3
"""
Real-time Vibration Analysis System
ESP32 S3 + ADXL345 + Isolation Forest ML

This script runs the complete system for real-time vibration detection.
"""

import subprocess
import sys
import time
import webbrowser
import os
from pathlib import Path

def check_dependencies():
    """Check if all required packages are installed"""
    required_packages = [
        'flask', 'flask-cors', 'pandas', 'numpy', 
        'scikit-learn', 'joblib', 'openpyxl', 'xlrd'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nInstall missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ All dependencies are installed!")
    return True

def check_data_files():
    """Check if required data files exist"""
    required_files = [
        "Dataset PCA (Normal 80 + Ringan 20).xlsx",
        "Dataset PCA (Normal 80 + Berat 20).xlsx"
    ]
    
    missing_files = []
    
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print("❌ Missing data files:")
        for file in missing_files:
            print(f"   - {file}")
        print("\nPlease ensure the Excel files are in the current directory.")
        return False
    
    print("✅ All data files found!")
    return True

def start_flask_server():
    """Start the Flask server"""
    print("\n🚀 Starting Flask server...")
    
    try:
        # Start Flask server in background
        server_process = subprocess.Popen([
            sys.executable, "realtime_vibration_server.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait a bit for server to start
        time.sleep(3)
        
        # Check if server is running
        if server_process.poll() is None:
            print("✅ Flask server started successfully!")
            print("   Server URL: http://localhost:5000")
            print("   Prediction endpoint: http://localhost:5000/predict")
            return server_process
        else:
            stdout, stderr = server_process.communicate()
            print("❌ Failed to start Flask server:")
            print(stderr.decode())
            return None
            
    except Exception as e:
        print(f"❌ Error starting Flask server: {e}")
        return None

def open_dashboard():
    """Open the web dashboard"""
    dashboard_path = Path("dashboard.html").absolute()
    
    if dashboard_path.exists():
        print("\n🌐 Opening dashboard...")
        webbrowser.open(f"file://{dashboard_path}")
        print("✅ Dashboard opened in browser!")
    else:
        print("❌ Dashboard file not found!")

def print_instructions():
    """Print setup instructions"""
    print("\n" + "="*60)
    print("🔧 SETUP INSTRUCTIONS")
    print("="*60)
    print("\n1. ESP32 S3 Setup:")
    print("   - Upload esp32_adxl345_realtime.ino to your ESP32 S3")
    print("   - Update WiFi credentials in the code")
    print("   - Update server URL to your computer's IP address")
    print("   - Connect ADXL345 sensor to ESP32 S3")
    print("\n2. Hardware Connections:")
    print("   - VCC → 3.3V")
    print("   - GND → GND")
    print("   - SCL → GPIO22")
    print("   - SDA → GPIO21")
    print("   - CS → 3.3V (for I2C mode)")
    print("   - SDO → GND (for address 0x53)")
    print("\n3. ESP32 Commands:")
    print("   - START: Start measurement")
    print("   - STOP: Stop measurement")
    print("   - CALIBRATE: Recalibrate sensor")
    print("   - PREDICT: Manual prediction request")
    print("\n4. Dashboard Features:")
    print("   - Real-time vibration status")
    print("   - Confidence levels")
    print("   - Vibration trend charts")
    print("   - System controls")
    print("\n5. Troubleshooting:")
    print("   - Check WiFi connection")
    print("   - Verify server IP address")
    print("   - Ensure sensor is properly connected")
    print("   - Check Serial Monitor for ESP32 status")
    print("="*60)

def main():
    """Main function"""
    print("🔍 Real-time Vibration Analysis System")
    print("ESP32 S3 + ADXL345 + Isolation Forest ML")
    print("="*50)
    
    # Check dependencies
    if not check_dependencies():
        return
    
    # Check data files
    if not check_data_files():
        return
    
    # Print instructions
    print_instructions()
    
    # Start Flask server
    server_process = start_flask_server()
    if not server_process:
        return
    
    # Open dashboard
    open_dashboard()
    
    print("\n🎯 System is ready!")
    print("   - Flask server: http://localhost:5000")
    print("   - Dashboard: dashboard.html")
    print("   - ESP32 should connect automatically")
    print("\nPress Ctrl+C to stop the server...")
    
    try:
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        if server_process:
            server_process.terminate()
            server_process.wait()
        print("✅ Server stopped. Goodbye!")

if __name__ == "__main__":
    main() 