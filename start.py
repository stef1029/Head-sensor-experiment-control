import subprocess
import serial
import time
import keyboard
import os
from datetime import datetime
import json
from colorama import init, Fore, Back, Style
init()

from utils.experiment_control_class import ExperimentControl

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
    