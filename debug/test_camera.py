#!/usr/bin/env python3

import os
import subprocess
import datetime
import time

# ========== DEFINE ALL VARIABLES HERE ==========
# Path to camera executable (CHANGE THIS)
CAMERA_EXE_PATH = r"C:\Behaviour\Camera\x64\Release\Camera_to_binary.exe"

# Mouse ID
MOUSE_ID = "test1"

# Output directory (CHANGE THIS)
OUTPUT_PATH = r"C:\dev\projects\Head-sensor-experiment-control\Debug_scripts\outputs"

# Camera settings
SERIAL_NUMBER = "24174020"  # openfield camera
FPS = 60
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600

# How long to run (in seconds)
DURATION = 10
# ===============================================

def run_camera_test():
    """Run the camera tracking executable with predefined variables"""
    
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    
    # Get current date/time for the command
    date_time = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
    
    # Build the command
    cmd = [
        CAMERA_EXE_PATH,
        "--id", MOUSE_ID,
        "--date", date_time,
        "--path", OUTPUT_PATH,
        "--serial_number", SERIAL_NUMBER,
        "--fps", str(FPS),
        "--windowWidth", str(WINDOW_WIDTH),
        "--windowHeight", str(WINDOW_HEIGHT)
    ]
    
    print(f"Starting camera with command: {' '.join(cmd)}")
    
    # Start the process
    process = subprocess.Popen(cmd)
    
    print(f"Camera process started. Running for {DURATION} seconds...")
    
    # Wait for specified duration
    try:
        time.sleep(DURATION)
    except KeyboardInterrupt:
        print("Test interrupted by user")
    
    # Create stop signal file
    stop_signal_path = os.path.join(OUTPUT_PATH, f"stop_camera_openfield.signal")
    with open(stop_signal_path, 'w') as f:
        pass
    
    print("Created stop signal file. Waiting for process to terminate...")
    
    # Wait for process to terminate
    try:
        process.wait(timeout=10)
        print("Camera process terminated successfully")
    except subprocess.TimeoutExpired:
        print("Process didn't terminate, forcing termination...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Process still running, killing it...")
            process.kill()
    
    print(f"Test complete. Output saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    run_camera_test()