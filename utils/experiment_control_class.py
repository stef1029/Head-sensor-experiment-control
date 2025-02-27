import subprocess
import serial
import time
import keyboard
import os
from datetime import datetime
import json
from colorama import init, Fore, Style
import sys

from utils import countdown_timer, check_for_signal_file, delete_signal_files, create_end_signal

init()

class ExperimentControl:
    def __init__(self, config_path=r"C:\dev\projects\head_sensor_config.json"):
        self.config_path = config_path
        
        # Default COM ports (editable)
        self.stim_board_port = 'COM23'
        self.head_sensor_port = 'COM24'
        self.arduino_daq_port = 'COM2'
        self.laser_port = 'COM11'
        
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
        
        # Will be assigned in run_experiment
        self.channel_list = None

    def load_config(self):
        with open(self.config_path, "r") as file:
            config = json.load(file)
        self.python_exe = config.get("PYTHON_PATH")
        self.timer_path = config.get("TIMER_SCRIPT")
        self.head_sensor_script = config.get("HEAD_SENSOR_SCRIPT")
        self.arduino_daq_path = config.get("SERIAL_LISTEN")
        self.camera_exe = config.get("BEHAVIOUR_CAMERA")
        self.laser_control = str(config.get("LASER_CONTROL_SCRIPT"))

    def start_stim_board(self, set_laser_powers, stim_times_ms, num_cycles, stim_delay):
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
        signal_file = os.path.join(self.output_path, "stim_complete.signal")
        with open(signal_file, 'w') as f:
            f.write("Stim experiment complete")

    def stop_camera(self, cam_no):
        signal_file = os.path.join(self.output_path, f"stop_camera_{cam_no}.signal")
        with open(signal_file, 'w') as f:
            f.write("Stop camera recording")

    def setup_experiment_folder(self, output_folder, mouse_id):
        self.date_time = f"{datetime.now():%y%m%d_%H%M%S}"
        self.foldername = f"{self.date_time}_{mouse_id}"
        self.output_path = os.path.join(output_folder, self.foldername)
        os.mkdir(self.output_path)

    def get_laser_parameters(self):
        print(Fore.GREEN + "Make sure that laser is set to Modulation mode and 'Digital' box is checked." +
              Style.RESET_ALL)
        set_laser_power = input("Enter laser power (computer value) (mW): ")
        brain_laser_power = input("Enter laser power (at brain) (mW): ")
        return set_laser_power, brain_laser_power

    def start_arduino_daq(self):
        """Start Arduino DAQ process, passing channel_list as a comma-separated string."""
        self.arduino_DAQ_process = subprocess.Popen([
            self.python_exe, self.arduino_daq_path,
            '--id', self.mouse_id,
            '--date', self.date_time,
            '--path', self.output_path,
            '--port', self.arduino_daq_port,
            '--channels', ",".join(self.channel_list)
        ])

        # Name of the signal file that the DAQ script will create
        daq_signal_file = os.path.join(self.output_path, "daq_started.signal")
        # Block until the DAQ signal file appears
        while not os.path.exists(daq_signal_file):
            time.sleep(0.5)
        
        os.remove(daq_signal_file)
        print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Arduino DAQ script started.")

    def start_camera_tracking(self):
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
        self.head_sensor_process = subprocess.Popen([
            self.python_exe, self.head_sensor_script,
            '--id', self.mouse_id,
            '--date', self.date_time,
            '--path', self.output_path,
            '--port', self.head_sensor_port,
            '--rotation', str(self.rotation_angle)
        ])
        print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Head sensor script started.")

    def wait_for_completion(self):
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
        if stim_port:
            self.stim_board_port = stim_port
        if head_port:
            self.head_sensor_port = head_port
        if daq_port:
            self.arduino_daq_port = daq_port
        if laser_port:
            self.laser_port = laser_port

    def run_experiment(
        self,
        output_folder,
        mouse_id,
        channel_list,
        set_laser_powers=None, 
        brain_laser_powers=None,
        stim_times_ms=None,
        num_cycles=None,
        stim_delay=None,
        pulse_freq=0,
        pulse_on_time=50,
        rotation_angle=90,
        notes="",
        run_head_sensor=True,
        run_camera=True,
        run_arduino_daq=True,
        run_stim_board=True
    ):
        """Main method to run the experiment, requiring exactly 8 channel names."""

        # Check channel_list
        if not isinstance(channel_list, list) or len(channel_list) != 8:
            raise ValueError("channel_list must be a list of exactly 8 channel names.")
        self.channel_list = channel_list
        
        self.run_head_sensor = run_head_sensor
        self.run_camera = run_camera
        self.run_arduino_daq = run_arduino_daq
        self.run_stim_board = run_stim_board

        if stim_times_ms is None:
            stim_times_ms = [50, 100, 250, 500, 1000, 2000]
        if num_cycles is None:
            num_cycles = 20
        if stim_delay is None:
            stim_delay = "5s"

        if set_laser_powers is None or brain_laser_powers is None:
            set_laser_powers, brain_laser_powers = self.get_laser_parameters()

        self.rotation_angle = rotation_angle
        self.mouse_id = mouse_id
        self.setup_experiment_folder(output_folder, mouse_id)

        self.start_time = time.perf_counter()
        
        # Start the timer
        self.timer_process = subprocess.Popen([self.python_exe, self.timer_path], shell=False)
        time.sleep(2)
        
        # Start other processes
        if self.run_arduino_daq:
            self.start_arduino_daq()
        if self.run_camera:
            self.start_camera_tracking()
        if self.run_head_sensor:
            self.start_head_sensor()
        
        if self.run_stim_board:
            countdown_timer(10, message="Starting laser control board")
            self.start_stim_board_test(
                set_laser_powers,
                stim_times_ms,
                num_cycles,
                stim_delay,
                pulse_freq=pulse_freq,
                pulse_on_time=pulse_on_time
            )
            self.laser_control_process.wait()
            self.create_stim_signal()

        if self.run_head_sensor:
            self.head_sensor_process.wait()
            self.stop_camera(4)
        if self.run_camera:
            self.camera_process.wait()
        
        self.wait_for_completion()
        
        self.end_time = time.perf_counter()
        
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
    # Example usage
    output_folder = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output"
    config_path = r"C:\dev\projects\head_sensor_config.json"

    mouse_id = "test1"
    
    # Channel list must have exactly 8 entries
    example_channel_list = [
        "IN3V3_2_camera",
        "IN3V3_3",
        "IN3V3_4",
        "IN3V3_5",
        "IN5V_6_head_sensor",
        "IN5V_7_laser",
        "IN5V_8",
        "IN5V_9"
    ]

    experiment = ExperimentControl(config_path=config_path)
    experiment.configure_ports(
        stim_port='COM23',
        head_port='COM24',
        daq_port='COM18',
        laser_port='COM11'
    )

    experiment.run_experiment(
        output_folder=output_folder,
        mouse_id=mouse_id,
        channel_list=example_channel_list
    )
