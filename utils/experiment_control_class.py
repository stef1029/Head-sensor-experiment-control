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
    def __init__(self, config_path=r"C:\Dev\projects\Head-sensor-experiment-control\config\head_sensor_config.json"):
        self.config_path = config_path
        
        # Board tag names (human-readable, resolved via board registry)
        self.stim_board_tag = 'laser_pulse_board'
        self.head_sensor_tag = 'head_imu'
        self.body_sensor_tag = 'body_imu'
        self.arduino_daq_tag = 'imu_exp_daq'
        self.laser_tag_473nm = '473_laser_1'
        self.laser_tag_635nm = '635nm_laser_1'
        
        self.baud_rate = 57600
        self.timeout = 2
        self.stim_board = None
        self.load_config()
        
        # Default camera settings
        self.fps = 30
        self.window_width = 640
        self.window_height = 512


    def load_config(self):
        with open(self.config_path, "r") as file:
            config = json.load(file)
        self.python_exe = config.get("PYTHON_PATH")
        self.timer_path = config.get("TIMER_SCRIPT")
        self.head_sensor_script = config.get("HEAD_SENSOR_SCRIPT")
        self.arduino_daq_path = config.get("SERIAL_LISTEN")
        self.camera_exe = config.get("BEHAVIOUR_CAMERA")
        self.laser_control_473nm = str(config.get("LASER_CONTROL_SCRIPT"))
        self.laser_control_635nm = str(config.get("RED_LASER_CONTROL_SCRIPT",
            r"C:\Dev\projects\Head-sensor-experiment-control\red_laser_control.py"))
        
        # Board registry path
        registry_path = config.get("BOARD_REGISTRY")
        if not registry_path:
            raise FileNotFoundError(
                f"Config '{self.config_path}' does not contain a 'BOARD_REGISTRY' key."
            )
        self.registry_path = registry_path

    def start_stim_board(self, set_laser_powers, stim_times_ms, num_cycles, stim_delay, laser_wavelength='473nm'):
        powers_args = [str(p) for p in set_laser_powers] if isinstance(set_laser_powers, list) else [str(set_laser_powers)]
        stim_times_args = [str(t) for t in stim_times_ms] if isinstance(stim_times_ms, list) else [str(stim_times_ms)]

        # Select the appropriate laser control script and tag
        if laser_wavelength == '473nm':
            laser_script = self.laser_control_473nm
            laser_tag = self.laser_tag_473nm
        else:
            laser_script = self.laser_control_635nm
            laser_tag = self.laser_tag_635nm

        self.laser_control_process = subprocess.Popen([
            self.python_exe, laser_script,
            '--registry', self.registry_path,
            '--laser_board', laser_tag,
            '--arduino_board', self.stim_board_tag,
            '--powers'] + powers_args +
            ['--stim_times'] + stim_times_args +
            ['--num_cycles', str(num_cycles),
             '--stim_delay', str(stim_delay)]
        )

    def start_stim_board_test(self, set_laser_powers, stim_times_ms, num_cycles, stim_delay, pulse_freq=0, pulse_on_time=50, laser_wavelength='473nm'):
        powers_args = [str(p) for p in set_laser_powers] if isinstance(set_laser_powers, list) else [str(set_laser_powers)]
        stim_times_args = [str(t) for t in stim_times_ms] if isinstance(stim_times_ms, list) else [str(stim_times_ms)]

        # Select the appropriate laser control script and tag
        if laser_wavelength == '473nm':
            laser_script = self.laser_control_473nm
            laser_tag = self.laser_tag_473nm
        else:
            laser_script = self.laser_control_635nm
            laser_tag = self.laser_tag_635nm

        self.laser_control_process = subprocess.Popen([
            self.python_exe, laser_script,
            '--registry', self.registry_path,
            '--laser_board', laser_tag,
            '--arduino_board', self.stim_board_tag,
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
            '--registry', self.registry_path,
            '--board', self.arduino_daq_tag,
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
            "--serial_number", self.camera_serial_number,
            "--fps", str(self.fps),
            "--windowWidth", str(self.window_width),
            "--windowHeight", str(self.window_height)
        ]
        self.camera_process = subprocess.Popen(tracker_command)
        print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Camera tracking started.")

    def start_imu_sensor(self, board_tag, 
                         signal_name, 
                         rotation_angle, 
                         sensor_location="head"):
        imu_process = subprocess.Popen([
            self.python_exe, self.head_sensor_script,
            '--id', self.mouse_id,
            '--date', self.date_time,
            '--path', self.output_path,
            '--registry', self.registry_path,
            '--board', board_tag,
            '--rotation', str(rotation_angle),
            '--sensor_location', sensor_location,
        ])
        print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + f" {sensor_location.capitalize()} sensor script started ({board_tag}).")
        return imu_process

    def wait_for_completion(self):
        while True:
            if check_for_signal_file(self.output_path, "head_sensor"):
                time.sleep(1)
                break
            time.sleep(0.5)
        create_end_signal(self.output_path, "behaviour_control")

    def save_metadata(self,
                        output_folder,
                        mouse_id,
                        channel_list,
                        camera_serial_number="24174020",
                        camera_fps=30,
                        video_window_width=640,
                        video_window_height=512,
                        set_laser_powers=None,
                        brain_laser_powers=None,
                        stim_times_ms=None,
                        num_cycles=None,
                        stim_delay=None,
                        pulse_freq=0,
                        pulse_on_time=50,
                        head_sensor_rotation_angle=90,
                        body_sensor_rotation_angle=0,
                        notes="",
                        run_head_sensor=True,
                        run_body_sensor=False,
                        run_camera=True,
                        run_arduino_daq=True,
                        run_stim_board=True,
                        laser_wavelength='473nm'
                      ):
        metadata_filename = os.path.join(self.output_path, f"{self.foldername}_metadata.json")

        metadata = {
            'output_folder': output_folder,
            'mouse_id': mouse_id,
            'channel_list': channel_list,
            'camera_serial_number': camera_serial_number,
            'camera_fps': camera_fps,
            'video_window_width': video_window_width,
            'video_window_height': video_window_height,
            'set_laser_power_mW': set_laser_powers,
            'brain_laser_power_mW': brain_laser_powers,
            'laser_wavelength': laser_wavelength,
            'stim_times_ms': stim_times_ms,
            'num_cycles': num_cycles,
            'stim_delay': stim_delay,
            'pulse_freq': pulse_freq,
            'pulse_on_time': pulse_on_time,
            'head_sensor_rotation_angle': head_sensor_rotation_angle,
            'body_sensor_rotation_angle': body_sensor_rotation_angle,
            'experiment_duration': f"{round((self.end_time - self.start_time) // 60)}m "
                                   f"{round((self.end_time - self.start_time) % 60)}s",
            'notes': notes,
            'run_head_sensor': run_head_sensor,
            'run_body_sensor': run_body_sensor,
            'run_camera': run_camera,
            'run_arduino_daq': run_arduino_daq,
            'run_stim_board': run_stim_board,
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

    def configure_boards(self, stim_board=None, head_sensor=None, body_sensor=None, 
                         daq_board=None, laser_473nm=None, laser_635nm=None):
        """Set board tag names (human-readable names from board_registry.json)."""
        if stim_board:
            self.stim_board_tag = stim_board
        if head_sensor:
            self.head_sensor_tag = head_sensor
        if body_sensor:
            self.body_sensor_tag = body_sensor
        if daq_board:
            self.arduino_daq_tag = daq_board
        if laser_473nm:
            self.laser_tag_473nm = laser_473nm
        if laser_635nm:
            self.laser_tag_635nm = laser_635nm

    def run_experiment(
        self,
        output_folder,
        mouse_id,
        channel_list,
        camera_serial_number="24174020",
        camera_fps=30,
        video_window_width=640,
        video_window_height=512,
        set_laser_powers=None,
        brain_laser_powers=None,
        stim_times_ms=None,
        num_cycles=None,
        stim_delay=None,
        pulse_freq=0,
        pulse_on_time=50,
        head_sensor_rotation_angle=90,
        body_sensor_rotation_angle=0,
        notes="",
        run_head_sensor=True,
        run_body_sensor=False,
        run_camera=True,
        run_arduino_daq=True,
        run_stim_board=True,
        laser_wavelength='473nm'
    ):
        """Main method to run the experiment, requiring exactly 8 channel names."""

        # Check channel_list
        if not isinstance(channel_list, list) or len(channel_list) != 8:
            raise ValueError("channel_list must be a list of exactly 8 channel names.")
        self.channel_list = channel_list

        self.camera_serial_number = camera_serial_number
        self.fps = camera_fps
        self.window_width = video_window_width
        self.window_height = video_window_height
        
        self.run_head_sensor = run_head_sensor
        self.run_body_sensor = run_body_sensor
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

        self.head_sensor_rotation_angle = head_sensor_rotation_angle
        self.body_sensor_rotation_angle = body_sensor_rotation_angle
        self.mouse_id = mouse_id
        self.setup_experiment_folder(output_folder, mouse_id)

        self.start_time = time.perf_counter()
        
        # Start the timer
        self.timer_process = subprocess.Popen([self.python_exe, self.timer_path], shell=False)
        time.sleep(2)
        
        # Start other processes
        if self.run_arduino_daq:
            self.start_arduino_daq()    # Starts serial listen script/ DAQ and waits until that script makes a signal file
        if self.run_camera:
            self.start_camera_tracking()
        if self.run_head_sensor:
            self.head_sensor_process = self.start_imu_sensor(board_tag=self.head_sensor_tag, 
                                  signal_name="head_sensor",
                                  rotation_angle=self.head_sensor_rotation_angle,
                                  sensor_location="head",)
        if self.run_body_sensor:
            self.body_sensor_process = self.start_imu_sensor(board_tag=self.body_sensor_tag, 
                                  signal_name="body_sensor",
                                  rotation_angle=self.body_sensor_rotation_angle,
                                  sensor_location="body",)
        
        if self.run_stim_board:
            countdown_timer(10, message="Starting laser control board")
            self.start_stim_board_test(
                set_laser_powers,
                stim_times_ms,
                num_cycles,
                stim_delay,
                pulse_freq=pulse_freq,
                pulse_on_time=pulse_on_time,
                laser_wavelength=laser_wavelength
            )
            self.laser_control_process.wait()   # if using laser control board, wait for it to finish
            self.create_stim_signal()   # write signal file to indicate stim is complete

        if self.run_head_sensor:
            self.head_sensor_process.wait()  # wait for head sensor to finish (either via stim board signal or exit_key)
            self.stop_camera("openfield")   # create signal file to stop camera recording
        if self.run_body_sensor:
            self.body_sensor_process.wait()  # wait for body sensor to finish (either via stim board signal or exit_key)
            
        if self.run_camera:
            self.camera_process.wait()  # wait until the camera process finishes (either via head sensor signal or exit_key)
        
        self.wait_for_completion()

        self.arduino_DAQ_process.wait()  # wait until DAQ process finishes
        print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Arduino DAQ script finished.")
        
        self.end_time = time.perf_counter()
        
        self.save_metadata(
            output_folder=output_folder,
            mouse_id=mouse_id,
            channel_list=channel_list,
            camera_serial_number=camera_serial_number,
            camera_fps=camera_fps,
            video_window_width=video_window_width,
            video_window_height=video_window_height,
            set_laser_powers=set_laser_powers,
            brain_laser_powers=brain_laser_powers,
            stim_times_ms=stim_times_ms,
            num_cycles=num_cycles,
            stim_delay=stim_delay,
            pulse_freq=pulse_freq,
            pulse_on_time=pulse_on_time,
            head_sensor_rotation_angle=head_sensor_rotation_angle,
            body_sensor_rotation_angle=body_sensor_rotation_angle,
            notes=notes,
            run_head_sensor=run_head_sensor,
            run_body_sensor=run_body_sensor,
            run_camera=run_camera,
            run_arduino_daq=run_arduino_daq,
            run_stim_board=run_stim_board,
            laser_wavelength=laser_wavelength
        )

        
        self.cleanup_processes()
        print(Fore.MAGENTA + "Experiment control:" + Style.RESET_ALL + "Experiment finished running.\a")

