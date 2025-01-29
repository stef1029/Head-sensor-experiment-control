import subprocess
import serial
import time
import keyboard
import os
from datetime import datetime
import json
from colorama import init, Fore, Back, Style
import sys

from utils import countdown_timer, check_for_signal_file, delete_signal_files, create_end_signal

init()

class ExperimentControl:
    def __init__(self, config_path=r"C:\dev\projects\head_sensor_config.json"):
        self.config_path = config_path
        # Make COM ports more obvious and configurable
        self.stim_board_port = 'COM23'  # STIM BOARD PORT - CHANGE THIS AS NEEDED
        self.head_sensor_port = 'COM24'  # HEAD SENSOR PORT - CHANGE THIS AS NEEDED
        self.arduino_daq_port = 'COM2'   # ARDUINO DAQ PORT - CHANGE THIS AS NEEDED
        self.laser_port = 'COM11'        # LASER CONTROL PORT - CHANGE THIS AS NEEDED
        
        self.baud_rate = 57600
        self.timeout = 2
        self.exit_key = 'esc'
        self.stim_board = None
        self.load_config()
        
        # Default camera settings
        self.fps = 30
        self.window_width = 640
        self.window_height = 512
        
        # Initialize process handlers
        self.arduino_DAQ_process = None
        self.camera_process = None
        self.timer_process = None
        self.head_sensor_process = None
        
        # Initialize experiment parameters
        self.start_time = None
        self.end_time = None
        self.output_path = None
        self.date_time = None
        self.foldername = None

    def load_config(self):
        """Load configuration from JSON file"""
        with open(self.config_path, "r") as file:
            config = json.load(file)
            
        self.python_exe = config.get("PYTHON_PATH")
        self.timer_path = config.get("TIMER_SCRIPT")
        self.head_sensor_script = config.get("HEAD_SENSOR_SCRIPT")
        self.arduino_daq_path = config.get("SERIAL_LISTEN")
        self.camera_exe = config.get("BEHAVIOUR_CAMERA")
        self.laser_control = str(config.get("LASER_CONTROL_SCRIPT"))

    def start_stim_board(self, set_laser_powers, stim_times_ms, num_cycles, stim_delay):
        """Initialize and start the stimulation board"""
        powers_args = [str(p) for p in set_laser_powers] if isinstance(set_laser_powers, list) else [str(set_laser_powers)]
        stim_times_args = [str(t) for t in stim_times_ms] if isinstance(stim_times_ms, list) else [str(stim_times_ms)]

        self.laser_control_process = subprocess.Popen([
            self.python_exe, self.laser_control,
            '--laser_port', self.laser_port,
            '--arduino_port', self.stim_board_port,
            '--powers'] + powers_args +
            ['--stim_times'] + stim_times_args +
            ['--num_cycles', str(num_cycles),
            '--stim_delay', str(stim_delay)]
        )

    def start_stim_board_test(self, set_laser_powers, stim_times_ms, num_cycles, stim_delay, pulse_freq=0, pulse_on_time=50):
        """Initialize and start the stimulation board
        
        Args:
            set_laser_powers: Single power value or list of powers in mW
            stim_times_ms: Single time value or list of stimulation times in ms
            num_cycles: Number of cycles to run
            stim_delay: Delay between stimulations in ms
            pulse_freq: Frequency in Hz for pulse train (0 for solid pulse)
            pulse_on_time: On time in milliseconds for each pulse
        """
        powers_args = [str(p) for p in set_laser_powers] if isinstance(set_laser_powers, list) else [str(set_laser_powers)]
        stim_times_args = [str(t) for t in stim_times_ms] if isinstance(stim_times_ms, list) else [str(stim_times_ms)]

        self.laser_control_process = subprocess.Popen([
            self.python_exe, self.laser_control,
            '--laser_port', self.laser_port,
            '--arduino_port', self.stim_board_port,
            '--powers'] + powers_args +
            ['--stim_times'] + stim_times_args +
            ['--num_cycles', str(num_cycles),
            '--stim_delay', str(stim_delay),
            '--pulse_freq', str(pulse_freq),
            '--pulse_on_time', str(pulse_on_time)]
        )

    def wait_for_stim_completion(self):
        self.laser_control_process.wait()

    def create_stim_signal(self):
        """Create a signal file to indicate stim experiment completion"""
        signal_file = os.path.join(self.output_path, "stim_complete.signal")
        with open(signal_file, 'w') as f:
            f.write("Stim experiment complete")

    def stop_camera(self, cam_no):
        """Create a signal file to stop the camera"""
        signal_file = os.path.join(self.output_path, f"stop_camera_{cam_no}.signal")
        with open(signal_file, 'w') as f:
            f.write("Stop camera recording")

    def setup_experiment_folder(self, output_folder, mouse_id):
        """Set up experiment parameters and create output directory"""
        self.date_time = f"{datetime.now():%y%m%d_%H%M%S}"
        self.foldername = f"{self.date_time}_{mouse_id}"
        self.output_path = os.path.join(output_folder, self.foldername)
        os.mkdir(self.output_path)

    def get_laser_parameters(self):
        """Get laser parameters from user input"""
        print(Fore.GREEN + "Make sure that laser is set to Modulation mode and 'Digital' box is checked." + 
              Style.RESET_ALL)
        set_laser_power = input("Enter laser power (computer value) (mW): ")
        brain_laser_power = input("Enter laser power (at brain) (mW): ")
        return set_laser_power, brain_laser_power

    def start_arduino_daq(self):
        """Start Arduino DAQ process"""
        self.arduino_DAQ_process = subprocess.Popen([
            self.python_exe, self.arduino_daq_path,
            '--id', self.mouse_id,
            '--date', self.date_time,
            '--path', self.output_path,
            '--port', self.arduino_daq_port  # Add COM port argument
        ])
        countdown_timer(10, message="Starting ArduinoDAQ")

    def start_camera_tracking(self):
        """Start camera tracking process"""
        tracker_command = [
            self.camera_exe,
            "--id", self.mouse_id,
            "--date", self.date_time,
            "--path", self.output_path,
            "--rig", "4",
            "--fps", str(self.fps),
            "--windowWidth", str(self.window_width),
            "--windowHeight", str(self.window_height)
        ]
        self.camera_process = subprocess.Popen(tracker_command)
        print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Camera tracking started.")

    def start_head_sensor(self):
        """Start head sensor script with rotation angle"""
        self.head_sensor_process = subprocess.Popen([
            self.python_exe, self.head_sensor_script,
            '--id', self.mouse_id,
            '--date', self.date_time,
            '--path', self.output_path,
            '--port', self.head_sensor_port,
            '--rotation', str(self.rotation_angle)  # Add rotation angle parameter
        ])
        print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Head sensor script started.")


    def wait_for_completion(self):
        """Wait for experiment completion"""
        while True:
            if check_for_signal_file(self.output_path, "head_sensor"):
                time.sleep(1)
                break
            time.sleep(0.5)
        create_end_signal(self.output_path, "behaviour_control")

    def save_metadata(self, 
                    set_laser_power, 
                    brain_laser_power, 
                    stim_times_ms, 
                    num_cycles, 
                    stim_delay,
                    notes):
        """Save experiment metadata to JSON file"""
        metadata_filename = os.path.join(self.output_path, f"{self.foldername}_metadata.json")

        metadata = {
            'mouse_id': self.mouse_id,
            'set_laser_power_mW': set_laser_power,
            'brain_laser_power_mW': brain_laser_power,
            'stim_times_ms': stim_times_ms,
            'num_cycles': num_cycles,
            'stim_delay': stim_delay,
            'experiment_duration': f"{round((self.end_time - self.start_time) // 60)}m "
                                f"{round((self.end_time - self.start_time) % 60)}s",
            'notes': notes
        }

        with open(metadata_filename, 'w') as f:
            json.dump(metadata, f, indent=4)

    def cleanup_processes(self):
        """Clean up all running processes"""
        self.timer_process.terminate()
        processes = []
        if self.run_head_sensor:
            processes.append(self.head_sensor_process)
        if self.run_arduino_daq:
            processes.append(self.arduino_DAQ_process)
        if self.run_camera:
            processes.append(self.camera_process)
        if self.run_stim_board:
            processes.append(self.laser_control_process)
        for process in processes:
            if process:
                process.wait()
                process.terminate()
        
        delete_signal_files(self.output_path)

    def configure_ports(self, stim_port=None, head_port=None, daq_port=None, laser_port=None):
        """Configure COM ports for all devices"""
        if stim_port:
            self.stim_board_port = stim_port
        if head_port:
            self.head_sensor_port = head_port
        if daq_port:
            self.arduino_daq_port = daq_port
        if laser_port:
            self.laser_port = laser_port

    def run_experiment(self, 
                    output_folder, 
                    mouse_id,
                    set_laser_powers=None, 
                    brain_laser_powers=None,
                    stim_times_ms=None,
                    num_cycles=None,
                    stim_delay=None,
                    pulse_freq=0,
                    pulse_on_time=50,
                    rotation_angle=90, 
                    notes = "",
                    run_head_sensor=True,
                    run_camera=True,
                    run_arduino_daq=True,
                    run_stim_board=True):  
        """Main method to run the experiment"""

        self.run_head_sensor = run_head_sensor
        self.run_camera = run_camera
        self.run_arduino_daq = run_arduino_daq
        self.run_stim_board = run_stim_board

        # Allow default values if None
        if stim_times_ms is None:
            stim_times_ms = [50, 100, 250, 500, 1000, 2000]
        if num_cycles is None:
            num_cycles = 20
        if stim_delay is None:
            stim_delay = "5s"

        # If set_laser_power/brain_laser_power are not provided from the script,
        # you could still use the old prompt approach or set some defaults:
        if set_laser_powers is None or brain_laser_powers is None:
            set_laser_powers, brain_laser_powers = self.get_laser_parameters()  
            # or comment out the line above and do something else

        self.rotation_angle = rotation_angle
        self.mouse_id = mouse_id
        self.setup_experiment_folder(output_folder, mouse_id)  # see next section

        self.start_time = time.perf_counter()
        
        # Start the timer
        self.timer_process = subprocess.Popen([self.python_exe, self.timer_path], shell=False)
        time.sleep(2)  # Give timer a moment to start
        
        # Start other processes
        if self.run_arduino_daq:
            self.start_arduino_daq()
        if self.run_camera:
            self.start_camera_tracking()
        if self.run_head_sensor:
            self.start_head_sensor()
        
        if self.run_stim_board:
            countdown_timer(10, message="Starting laser control board")
            self.start_stim_board_test(set_laser_powers,
                                    stim_times_ms,
                                    num_cycles,
                                    stim_delay,
                                    pulse_freq=pulse_freq,
                                    pulse_on_time=pulse_on_time)
        
            # code pauses here until laser control finishes or esc pressed.
            self.laser_control_process.wait()
            self.create_stim_signal()

        if self.run_head_sensor:
            self.head_sensor_process.wait()
            self.stop_camera(4)
        if self.run_camera:
            self.camera_process.wait()
        
        self.wait_for_completion()
        
        self.end_time = time.perf_counter()
        
        # Save the metadata with our flexible parameters
        self.save_metadata(
            set_laser_powers,
            brain_laser_powers,
            stim_times_ms,
            num_cycles,
            stim_delay,
            notes
        )
        
        self.cleanup_processes()
        print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Experiment finished running.")



if __name__ == "__main__":
    output_folder = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output"
    config_path = r"C:\dev\projects\head_sensor_config.json"

    mouse_id = "test1"
    
    # Initialize experiment control with specific COM ports
    experiment = ExperimentControl(config_path)
    
    # Configure COM ports - ADJUST THESE AS NEEDED
    experiment.configure_ports(
        stim_port='COM23',    # Stim board
        head_port='COM24',    # Head sensor
        daq_port='COM18'       # Arduino DAQ
    )
    
    experiment.run_experiment(output_folder, mouse_id)