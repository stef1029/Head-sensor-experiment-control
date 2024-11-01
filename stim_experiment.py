import subprocess
import serial
import time
import keyboard
import os
from datetime import datetime
import json

# Configuration
head_sensor_script = r'C:\Users\Tripodi Group\OneDrive - University of Cambridge\01 - PhD at LMB\Coding projects\240520 - IMU python\head_sensor.py'  # Path to your head sensor script
camera_script = r"C:\Users\Tripodi Group\OneDrive - University of Cambridge\01 - PhD at LMB\Coding projects\240520 - IMU python\Camera.py"
stim_board_port = 'COM23'
baud_rate = 57600
timeout = 2

def start_stim_board():
    try:
        stim_board = serial.Serial(stim_board_port, baud_rate, timeout=timeout)
        time.sleep(2)
        stim_board.write(b's')
    except serial.SerialException:
        print("Stim board startup error, trying again...")
        time.sleep(2)
        stim_board = serial.Serial(stim_board_port, baud_rate, timeout=timeout)
        time.sleep(2)
        stim_board.write(b's')

    return stim_board


def main():
    # Prompt user for mouse ID
    output_folder = r"C:\Users\Tripodi Group\Videos\Head_sensor_output"
    mouse_id = input("Enter mouse ID: ")

    # Metadata:
    set_laser_power = input("Enter laser power (computer value) (mW): ")
    brain_laser_power = input("Enter laser power (at brain) (mW): ")
    sync_signal_OEAB_channel = 7
    laser_OEAB_channel = 8
    stim_times = [10, 25, 50, 100, 150, 200, 250, 500, 1000]
    num_cycles = 20
    stim_delay = "10s"
    start_time = time.perf_counter()

    # Generate date_time and path
    date_time = f"{datetime.now():%y%m%d_%H%M%S}"
    foldername = f"{date_time}_{mouse_id}"
    output_path = os.path.join(output_folder, foldername)
    os.mkdir(output_path)
    input("Folder created. Start OEAB recording in this folder and press Enter to start the experiment.")
    #start camera:

    # camera_process = subprocess.Popen([
    #     'python', camera_script,
    #     '--id', mouse_id,
    #     '--date', date_time,
    #     '--path', output_path
    # ])

    # Start the head sensor script with the provided arguments
    head_sensor_process = subprocess.Popen([
        'python', head_sensor_script,
        '--id', mouse_id,
        '--date', date_time,
        '--path', output_path
    ])
    print("Head sensor script started.")
    time.sleep(10)
    
    # Start the stim board
    stim_board = start_stim_board()
    print("Stim board started.\n")
    
    # Listen for completion message from stim board
    while True:
        if stim_board.in_waiting > 0:
            message = stim_board.readline().decode('utf-8').strip()
            print(message)
            if message == 'e':
                print("Stim program completed. Press m to finish program.")
                stim_board.write(b'e')
                time.sleep(1)
                stim_board.close()
                break
        if keyboard.is_pressed('m'):
            print("User requested to stop the program.")
            stim_board.write(b'e')
            time.sleep(1)
            stim_board.close()
            break
            
    
    # Wait for the head sensor script to finish

    print("Head sensor script stopped.\n")
    print("OK to stop OEAB recording.")

    end_time = time.perf_counter()

    metadata_filename = os.path.join(output_path, "metadata.json")

    metadata = {'mouse_id': mouse_id,
                'set_laser_power_mW': set_laser_power,
                'brain_laser_power_mW': brain_laser_power,
                'sync_signal_OEAB_channel': sync_signal_OEAB_channel,
                'laser_OEAB_channel': laser_OEAB_channel,
                'stim_times_ms': stim_times,
                'num_cycles': num_cycles,
                'stim_delay': stim_delay,
                'experiment_duration': f"{round((end_time - start_time) // 60)}m {round((end_time - start_time) % 60)}s"}

    with open(metadata_filename, 'w') as f:
        json.dump(metadata, f, indent=4)

    head_sensor_process.wait()
    # camera_process.wait()

if __name__ == "__main__":
    main()
