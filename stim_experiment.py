import subprocess
import serial
import time
import keyboard
import os
from datetime import datetime
import json
from utils import countdown_timer, check_for_signal_file, delete_signal_files

# Configuration
stim_board_port = 'COM23'
baud_rate = 57600
timeout = 2
config_path = r"C:\dev\projects\head_sensor_config.json"
exit_key = 'esc' 

def main():

    with open(config_path, "r") as file:
        config = json.load(file)

    python_exe = config.get("PYTHON_PATH")
    timer_path = config.get("TIMER_SCRIPT")
    head_sensor_script = config.get("HEAD_SENSOR_SCRIPT")
    arduino_daq_path = config.get("SERIAL_LISTEN")

    # Prompt user for mouse ID
    output_folder = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output"

    mouse_id = "test1"
    # mouse_id = "test2"

    # Metadata:
    set_laser_power = input("Enter laser power (computer value) (mW): ")
    brain_laser_power = input("Enter laser power (at brain) (mW): ")
    # sync_signal_OEAB_channel = 7
    # laser_OEAB_channel = 8
    stim_times = [10, 25, 50, 100, 150, 200, 250, 500, 1000]
    num_cycles = 20
    stim_delay = "10s"
    start_time = time.perf_counter()

    # Generate date_time and path
    date_time = f"{datetime.now():%y%m%d_%H%M%S}"
    foldername = f"{date_time}_{mouse_id}"
    output_path = os.path.join(output_folder, foldername)
    os.mkdir(output_path)

    # start arduinoDAQ
    arduino_DAQ_process = subprocess.Popen([
        python_exe, arduino_daq_path,
        '--id', mouse_id,
        '--date', date_time,
        '--path', output_path
    ])
    # wait for daq to start:
    countdown_timer(10, message="Starting ArduinoDAQ")

    timer = subprocess.Popen([python_exe, timer_path], shell=False)

    # Start the head sensor script with the provided arguments
    head_sensor_process = subprocess.Popen([
        python_exe, head_sensor_script,
        '--id', mouse_id,
        '--date', date_time,
        '--path', output_path
    ])
    print("Head sensor script started.")
    time.sleep(10)
    
    # Listen for completion message from stim board
    while True:
        if keyboard.is_pressed(exit_key):
            print("User requested to stop the program.")
            # stim_board.write(b'e')
            time.sleep(1)
            # stim_board.close()
            break
            
    
    # Wait for the head sensor script to finish

    while True:
        if check_for_signal_file(output_path):
            # stim_board.write(b'e')  # Uncomment if needed
            time.sleep(1)
            # stim_board.close()  # Uncomment if needed
            break
        time.sleep(0.5)  # Check for the signal file every 0.5 seconds

    print("Head sensor script stopped.\n")

    end_time = time.perf_counter()

    metadata_filename = os.path.join(output_path, "metadata.json")

    metadata = {'mouse_id': mouse_id,
                'set_laser_power_mW': set_laser_power,
                'brain_laser_power_mW': brain_laser_power,
                # 'sync_signal_OEAB_channel': sync_signal_OEAB_channel,
                # 'laser_OEAB_channel': laser_OEAB_channel,
                'stim_times_ms': stim_times,
                'num_cycles': num_cycles,
                'stim_delay': stim_delay,
                'experiment_duration': f"{round((end_time - start_time) // 60)}m {round((end_time - start_time) % 60)}s"}

    with open(metadata_filename, 'w') as f:
        json.dump(metadata, f, indent=4)

    head_sensor_process.wait()
    arduino_DAQ_process.wait()
    timer.wait()

    delete_signal_files(output_path)

    # send signal from head sensor and camera that recording has stopped, to stop arduinoDAQ.

if __name__ == "__main__":
    main()
