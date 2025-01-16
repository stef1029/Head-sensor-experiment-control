import subprocess
import serial
import time
import keyboard
import os
from datetime import datetime
import json
from utils import countdown_timer, check_for_signal_file, delete_signal_files
from colorama import init, Fore, Back, Style

init()

# Configuration
stim_board_port = 'COM23'
baud_rate = 57600
timeout = 2
config_path = r"C:\dev\projects\head_sensor_config.json"
exit_key = 'esc' 

def start_stim_board():
    try:
        stim_board = serial.Serial(stim_board_port, baud_rate, timeout=timeout)
    except serial.SerialException as e:
        try:
            time.sleep(1)
            stim_board = serial.Serial(stim_board_port, baud_rate, timeout=timeout)
        except serial.SerialException as e:
            print(Fore.RED + f"Failed to connect to stim board on port {stim_board_port}." + Style.RESET_ALL)
            raise e
            
    print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + f"Connected to stim board on port {stim_board_port}.")
    time.sleep(2)
    stim_board.write(b's')  # Start the stim board
    return stim_board

def create_stim_signal(output_path):
    """Create a signal file to indicate stim experiment completion"""
    signal_file = os.path.join(output_path, "stim_complete.signal")
    with open(signal_file, 'w') as f:
        f.write("Stim experiment complete")

def main():
    with open(config_path, "r") as file:
        config = json.load(file)

    python_exe = config.get("PYTHON_PATH")
    timer_path = config.get("TIMER_SCRIPT")
    head_sensor_script = config.get("HEAD_SENSOR_SCRIPT")
    arduino_daq_path = config.get("SERIAL_LISTEN")
    camera_exe = config.get("BEHAVIOUR_CAMERA")  # Add this to your config file

    # Default camera settings
    fps = 30
    window_width = 640
    window_height = 512

    output_folder = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output"
    mouse_id = "test1"

    print(Fore.GREEN + "Make sure that laser is set to Modulation mode and 'Digital' box is checked." + Style.RESET_ALL)
    set_laser_power = input("Enter laser power (computer value) (mW): ")
    brain_laser_power = input("Enter laser power (at brain) (mW): ")
    stim_times = [10, 25, 50, 100, 150, 200, 250, 500, 1000]
    num_cycles = 20
    stim_delay = "10s"
    start_time = time.perf_counter()

    # Generate date_time and path
    date_time = f"{datetime.now():%y%m%d_%H%M%S}"
    foldername = f"{date_time}_{mouse_id}"
    output_path = os.path.join(output_folder, foldername)
    os.mkdir(output_path)

    # Start arduinoDAQ
    arduino_DAQ_process = subprocess.Popen([
        python_exe, arduino_daq_path,
        '--id', mouse_id,
        '--date', date_time,
        '--path', output_path
    ])
    # Wait for daq to start:
    countdown_timer(10, message="Starting ArduinoDAQ", print_message=False)

    # Start camera tracking
    tracker_command = [
        camera_exe,
        "--id", mouse_id,
        "--date", date_time,
        "--path", output_path,
        "--rig", "4",  # You might want to make this configurable
        "--fps", str(fps),
        "--windowWidth", str(window_width),
        "--windowHeight", str(window_height)
    ]
    camera_process = subprocess.Popen(tracker_command)
    print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Camera tracking started.")
    
    timer = subprocess.Popen([python_exe, timer_path], shell=False)

    # Start the head sensor script
    head_sensor_process = subprocess.Popen([
        python_exe, head_sensor_script,
        '--id', mouse_id,
        '--date', date_time,
        '--path', output_path
    ])
    print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Head sensor script started.")

    countdown_timer(10, message="Starting laser control board", print_message=False)

    stim_board = start_stim_board()
    
    # Listen for completion message from stim board
    while True:
        # check for e from stim board:
        if stim_board.in_waiting:
            if stim_board.read() == b'e':
                print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Received stop signal from stim board.")
                stim_board.close()
                create_stim_signal(output_path)  # Create signal file
                break
        if keyboard.is_pressed(exit_key):
            print("User requested to stop the program.")
            stim_board.write(b'e')
            stim_board.write(b'e')
            stim_board.write(b'e')
            time.sleep(1)
            stim_board.close()
            create_stim_signal(output_path)  # Create signal file
            break
            
    
    # Wait for the head sensor script to finish

    while True:

        if check_for_signal_file(output_path):
            time.sleep(1)
            break
        time.sleep(0.5)  # Check for the signal file every 0.5 seconds

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
    timer.terminate()

    delete_signal_files(output_path)

    # send signal from head sensor and camera that recording has stopped, to stop arduinoDAQ.

if __name__ == "__main__":
    main()
    print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Experiment finished running.")
