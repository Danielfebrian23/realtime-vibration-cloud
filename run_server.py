#!/usr/bin/env python3
"""
Simple script to run the Real-Time Vibration Analysis Server
"""

import sys
import subprocess
import time

def main():
    print("=" * 50)
    print("🚀 REAL-TIME VIBRATION ANALYSIS SERVER")
    print("=" * 50)
    print()
    print("Choose an option:")
    print("1. Run with Telegram bot (if available)")
    print("2. Run without Telegram bot (recommended)")
    print("3. Exit")
    print()
    
    while True:
        try:
            choice = input("Enter your choice (1-3): ").strip()
            
            if choice == "1":
                print("\nStarting server with Telegram bot...")
                print("Note: If there are conflicts, the server will continue without Telegram")
                subprocess.run([sys.executable, "realtime_vibration_server_clean.py"])
                break
            elif choice == "2":
                print("\nStarting server without Telegram bot...")
                subprocess.run([sys.executable, "realtime_vibration_server_clean.py", "--no-telegram"])
                break
            elif choice == "3":
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please enter 1-3.")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main() 