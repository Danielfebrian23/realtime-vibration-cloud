#!/usr/bin/env python3
"""
Startup script for Real-Time Vibration Analysis Server
"""

import sys
import os
import subprocess
import time

def print_banner():
    print("=" * 60)
    print("🚀 REAL-TIME VIBRATION ANALYSIS SERVER")
    print("=" * 60)
    print()

def print_options():
    print("Choose an option:")
    print("1. Start server with Telegram bot")
    print("2. Start server without Telegram bot (recommended for testing)")
    print("3. Start server with Telegram bot (force restart)")
    print("4. Test server endpoints")
    print("5. Kill any running bot instances")
    print("6. Exit")
    print()

def kill_bot_instances():
    """Kill any running bot instances"""
    try:
        import psutil
        print("Checking for running bot instances...")
        
        bot_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any('realtime_vibration_server' in arg for arg in cmdline):
                    bot_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if bot_processes:
            print(f"Found {len(bot_processes)} running bot instances, terminating...")
            for proc in bot_processes:
                try:
                    proc.terminate()
                    print(f"Terminated process {proc.info['pid']}")
                except:
                    print(f"Failed to terminate process {proc.info['pid']}")
        else:
            print("No running bot instances found.")
        
        print("Bot instances cleared.")
        return True
    except ImportError:
        print("psutil not available. Please install it with: pip install psutil")
        return False

def test_server():
    """Test the server endpoints"""
    try:
        import requests
        import time
        
        print("Testing server endpoints...")
        base_url = "http://localhost:5000"
        
        # Test status
        try:
            response = requests.get(f"{base_url}/status", timeout=5)
            if response.status_code == 200:
                print("✅ Server is running!")
                data = response.json()
                print(f"   Status: {data.get('status')}")
                print(f"   Model loaded: {data.get('model_loaded')}")
                print(f"   Buffer size: {data.get('buffer_size')}")
                print(f"   Telegram available: {data.get('telegram_available', 'Unknown')}")
            else:
                print("❌ Server returned error status")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            return False
        
        # Test prediction
        dummy_data = {
            "x": [1.0, 1.1, 1.2, 1.3, 1.4],
            "y": [-10.0, -10.1, -10.2, -10.3, -10.4],
            "z": [1.8, 1.9, 2.0, 2.1, 2.2],
            "timestamp": int(time.time() * 1000)
        }
        
        try:
            response = requests.post(f"{base_url}/predict", 
                                   json=dummy_data,
                                   headers={'Content-Type': 'application/json'},
                                   timeout=5)
            if response.status_code == 200:
                result = response.json()
                print("✅ Prediction endpoint working!")
                print(f"   Severity: {result.get('severity')}")
                print(f"   Confidence: {result.get('confidence')}")
            else:
                print(f"❌ Prediction endpoint error: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Prediction test failed: {e}")
            return False
        
        print("✅ All tests passed!")
        return True
        
    except ImportError:
        print("requests not available. Please install it with: pip install requests")
        return False

def start_server(use_telegram=True, force_restart=False):
    """Start the server"""
    if force_restart:
        print("Killing any existing bot instances...")
        kill_bot_instances()
        time.sleep(2)
    
    print(f"Starting server {'with' if use_telegram else 'without'} Telegram bot...")
    
    if use_telegram:
        cmd = [sys.executable, "realtime_vibration_server_fixed.py"]
    else:
        cmd = [sys.executable, "realtime_vibration_server_fixed.py", "--no-telegram"]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except Exception as e:
        print(f"Error starting server: {e}")

def main():
    print_banner()
    
    while True:
        print_options()
        
        try:
            choice = input("Enter your choice (1-6): ").strip()
            
            if choice == "1":
                start_server(use_telegram=True)
            elif choice == "2":
                start_server(use_telegram=False)
            elif choice == "3":
                start_server(use_telegram=True, force_restart=True)
            elif choice == "4":
                test_server()
            elif choice == "5":
                kill_bot_instances()
            elif choice == "6":
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please enter 1-6.")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main() 