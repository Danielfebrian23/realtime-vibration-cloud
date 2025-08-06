import psutil
import os

def check_bot_instances():
    """Check for running Python processes that might be bot instances"""
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
        print(f"Found {len(bot_processes)} running bot instances:")
        for proc in bot_processes:
            print(f"  PID: {proc.info['pid']}, Command: {' '.join(proc.info['cmdline'])}")
        
        response = input("\nDo you want to terminate these processes? (y/n): ")
        if response.lower() == 'y':
            for proc in bot_processes:
                try:
                    proc.terminate()
                    print(f"Terminated process {proc.info['pid']}")
                except:
                    print(f"Failed to terminate process {proc.info['pid']}")
    else:
        print("No running bot instances found.")
    
    print("\nYou can now start the server safely.")

if __name__ == "__main__":
    check_bot_instances() 