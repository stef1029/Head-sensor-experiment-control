from datetime import datetime
import subprocess
import sys
import json
import os

from utils.experiment_control_class import ExperimentControl

if __name__ == "__main__":
    config_path = r"C:\dev\projects\head_sensor_config.json"
    
    # Load the configuration file to get the calibration script path
    with open(config_path, 'r') as f:
        config = json.load(f)
        calibration_script_path = config.get('CALIBRATION_SCRIPT', '')
    subprocess.run([sys.executable, calibration_script_path, "--info"], check=True)

    """
    Set mouse ID and implanted fiber transmission efficiency (TE) here
    """

    mouse_id = "T1"
    fiber_TE = 92

    # patch_cord_TE = 30 # 2025-09-24
    # patch_cord_TE = 64 # actual value
    # patch_cord_TE = 5 # Dan's one-time funky value
    # patch_cord_TE = 71 # Dan's value post-rotary joint
    # patch_cord_TE = 30 # cord 7 on array
    # patch_cord_TE = 34 # cord 1 on array
    # patch_cord_TE = 35 # cord 9 on array
    # patch_cord_TE = 40 # cord 6 on array
    patch_cord_TE = 20 # 2025-10-31






    """
    Chip direction selection (rotation angle):
    0 = chip left,
    90 = chip backward, 
    180 = chip right,
    270 = chip forward
    """

    """
    -------------- Set experiment parameters here ----------------------------------------------------------------
    """
    # output_folder = r"C:\DATA\251031_opto_Pitx2_excite_medulla"
    # # at_brain_power_levels = [0.5, 1, 2, 3, 5, 7, 10, 15]   
    # # stim_times_ms = [250] 
    # at_brain_power_levels = [10]   
    # stim_times_ms = [1000]       
    # num_cycles = 70
    # stim_delay = 5000
    # pulse_freq = 30 
    # pulse_on_time = 10
    # rotation_angle = 270 # chip forward
    # # # rotation_angle = 90 # chip backward
    # notes = "Pitx2::ChR2 fibers in pons, visual movement check"

    # output_folder = r"D:\Pitx2_Inhib_DTx\Baseline_movements\DCZ"
    # # at_brain_power_levels = [0.5, 1, 2, 3, 5, 7, 10, 15]   
    # # stim_times_ms = [250] 
    # at_brain_power_levels = [10]   
    # stim_times_ms = [1000]       
    # num_cycles = 3600
    # stim_delay = 1000
    # pulse_freq = 30 
    # pulse_on_time = 10
    # rotation_angle = 270 # chip forward
    # # # rotation_angle = 90 # chip backward
    # notes = "Pitx2 Chemogenetics: Baseline movement recording"

    
    # output_folder = r"c:\DATA\Pitx2_CatCh_Excite"
    # at_brain_power_levels = [0.1, 0.5, 1, 3, 5]      
    # stim_times_ms = [250, 1000]    
    # num_cycles = 50
    # stim_delay = 5000
    # pulse_freq = 30
    # pulse_on_time = 10
    # rotation_angle = 270 # chip forward
    # rotation_angle = 90 # chip backward
    # notes = "mtdl1.2c - Pitx2::CatCh test, forward chip, soft pilot"

    # output_folder = r"C:\DATA\251008_Pitx2-Catch-Array"
    # at_brain_power_levels = [0.1, 0.5, 1, 2, 3, 5, 7]      
    # stim_times_ms = [250]    
    # num_cycles = 70
    # stim_delay = 5000
    # pulse_freq = 30 
    # pulse_on_time = 10
    # rotation_angle = 270 # chip forward
    # # # rotation_angle = 90 # chip backward
    # notes = "Pitx2::CatCh test for array & head movement, forward chip, fibre #6"

    # output_folder = r"c:\DATA\250806_Pitx2_cFOS_opt"
    # at_brain_power_levels = [10]      
    # stim_times_ms = [1000]    
    # num_cycles = 600
    # stim_delay = 2000
    # pulse_freq = 30 
    # pulse_on_time = 10
    # rotation_angle = 270 # chip forward
    # # rotation_angle = 90 # chip backward
    # notes = "Pitx2::ChR2 test for cFOS expression, forward chip, soft pilot"


    # output_folder = r"C:\DATA\Pitx2_Chemo_Baseline_Movements"
    # at_brain_power_levels = [0]      
    # stim_times_ms = [900000]    
    # num_cycles = 1
    # stim_delay = 0
    # pulse_freq = 0
    # pulse_on_time = 0
    # rotation_angle = 0 # chip backward
    # notes = "mtao102-3c - test, uPSEM 817"

    # output_folder = r"C:\DATA\250515_opto_excite_Pitx2_VM"
    # at_brain_power_levels = [1, 5, 10, 20, 30]      
    # stim_times_ms = [100, 250, 500, 1000]    
    # num_cycles = 50
    # stim_delay = 5000
    # pulse_freq = 30
    # pulse_on_time = 10
    # rotation_angle = 90 # chip backward
    # notes = "mtaq14.1c - VM ctrl, backward chip"

    # output_folder = r"C:\DATA\250603_opto_excite_SC_sst"
    # at_brain_power_levels = [1, 3, 5, 10, 20]      
    # stim_times_ms = [100, 250, 500, 1000]    
    # num_cycles = 50
    # stim_delay = 5000
    # pulse_freq = 30
    # pulse_on_time = 10
    # rotation_angle = 180 # chip backward
    # notes = "mtbz8.3c - ChR2 in SC sst vGAT neurons, right chip"

    # output_folder = r"c:\20250405_Pitx2_opto_excite_headsensor"
    # at_brain_power_levels = [1, 3, 5, 10, 15, 20, 30]      
    # stim_times_ms = [50, 100, 250, 500, 1000, 2000]    
    # num_cycles = 20
    # stim_delay = 5000
    # pulse_freq = 30
    # pulse_on_time = 10
    # # rotation_angle = 270 # chip forward
    # rotation_angle = 90 # chip backward
    # notes = "mtaq14.1g - MD WT ctrl, backward chip"

    # output_folder = r"c:\DATA\250509_opto_inhibition_SC_sst"
    # at_brain_power_levels = [0.5, 0.8, 1, 2, 4, 6, 8, 10]      
    # stim_times_ms = [250, 500]    
    # num_cycles = 50
    # stim_delay = 5000
    # pulse_freq = 0
    # pulse_on_time = 0
    # rotation_angle = 180 
    # rotation_angle = 180 # chip right
    # notes = "Daniel's mouse with IC++ in SC sst vGAT neurons"

    # output_folder = r"C:\DATA\250423_opto_inhibition_SC_bilateral"
    # at_brain_power_levels = [1, 1.5, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16]      
    # stim_times_ms = [500, 2000]    
    # num_cycles = 20
    # stim_delay = 5000
    # pulse_freq = 0
    # pulse_on_time = 10
    # # rotation_angle = 270 # chip forward
    # rotation_angle = 90 # chip backward
    # notes = "right"

    """
    -------------- Set experiment parameters here ----------------------------------------------------------------
    """
    output_folder = r"D:\Pitx2_Inhib_DTx\Baseline_movements\DCZ"
    at_brain_power_levels = [5]      
    stim_times_ms = [1]    
    num_cycles = 1
    stim_delay = 3600000
    pulse_freq = 0
    pulse_on_time = 10
    head_sensor_rotation_angle = 90
    body_sensor_rotation_angle = 0
    notes = ""

    """
    -------------- Advanced setup (do not change or things will break): -------------------------------------------------
    """
    # Initialize experiment control
    experiment = ExperimentControl(config_path)

    # Configure COM ports - ADJUST THESE AS NEEDED
    experiment.configure_ports(
        stim_port='COM23',
        head_port='COM24',
        body_port='COM6',
        daq_port='COM19',
        laser_port='COM11'
    )

    # configure camera settings
    camera_serial_number = "24174020" 
    camera_fps = 30  
    video_window_width = 640
    video_window_height = 512

    # Turn items in experiment on/off
    run_head_sensor = True
    run_body_sensor = True
    run_camera = True
    run_arduino_daq = True
    run_stim_board = True

    # Channel list must have exactly 8 entries for the DAQ script
    channel_list = [
        "CAMERA_SYNC",
        "IN3V3_3",
        "IN3V3_4",
        "IN3V3_5",
        "HEADSENSOR_SYNC",
        "LASER_SYNC",
        "IN5V_8",
        "IN5V_9"
    ]

    """
    -------------- End of advanced setup. ------------------------------------------------------------------------
    """

    # Calculate laser intensities to achieve desired stim intensity at brain
    comp_power_levels = [round((power / (fiber_TE / 100)) / (patch_cord_TE / 100), 1)
                         for power in at_brain_power_levels]

    # Run the experiment
    experiment.run_experiment(
        output_folder=output_folder,
        set_laser_powers=comp_power_levels,
        brain_laser_powers=at_brain_power_levels,
        mouse_id=mouse_id,
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
        channel_list=channel_list,
        camera_serial_number=camera_serial_number,
        camera_fps=camera_fps
    )