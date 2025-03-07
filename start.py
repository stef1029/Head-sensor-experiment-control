from datetime import datetime

from utils.experiment_control_class import ExperimentControl

if __name__ == "__main__":
    config_path = r"C:\dev\projects\head_sensor_config.json"

    """
    Set mouse ID and implanted fiber transmission efficiency (TE) here
    """
    # mouse_id = "mtap16-2a" # left fiber 88%, right 89% - 1.72mW, 5.1, 8.6, 17.21
    # fiber_TE = 88
    # fiber_TE = 89

    # mouse_id = "mtap16-2b" # left fiber 86%, right 87% 
    # fiber_TE = 86
    # fiber_TE = 87

    # mouse_id = "mtaq15-1b" # fiber TE=96%
    # fiber_TE = 96

    # mouse_id = "mtaq15-1a" # fiber TE=96%
    # fiber_TE = 94

    # mouse_id = "mtaq11-2b" # fiber TE=96%
    # fiber_TE = 88

    # mouse_id = "mtaq15-1e" # fiber TE=96%
    # fiber_TE = 95

    # mouse_id = "mtaq15-1d" # fiber TE=96%
    # fiber_TE = 94

    # mouse_id = "mtaq16-1f" # fiber TE=96%
    # fiber_TE = 97

    # mouse_id = "mtaq16-1b" # fiber TE=96%
    # fiber_TE = 90

    # mouse_id = "mtaq14-1a" # fiber TE=88%
    # fiber_TE = 88

    # mouse_id = "mtaq14-1b" # fiber TE=91%
    # fiber_TE = 91

    # mouse_id = "mtaq14-1c" # fiber TE=70%
    # fiber_TE = 70

    mouse_id = "mtaq14-1c" # fiber TE=28%
    fiber_TE = 28

    # mouse_id = "test"
    # fiber_TE = 94


    patch_cord_TE = 59

    """
    -------------- Set experiment parameters here ----------------------------------------------------------------
    """
    output_folder = r"d:\1102_VM_opto_excite_headsensor"
    at_brain_power_levels = [0.1, 0.5, 1, 3, 5, 10]      
    stim_times_ms = [50, 100, 250, 500, 1000, 2000]     
    num_cycles = 20
    stim_delay = 5000
    pulse_freq = 30
    pulse_on_time = 10
    rotation_angle = 90
    notes = ""

    """
    -------------- Advanced setup (do not change): -------------------------------------------------
    """
    # Initialize experiment control
    experiment = ExperimentControl(config_path)

    # Configure COM ports - ADJUST THESE AS NEEDED
    experiment.configure_ports(
        stim_port='COM23',
        head_port='COM24',
        daq_port='COM19'
    )

    # Turn items in experiment on/off
    run_head_sensor = True
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
        rotation_angle=rotation_angle,
        notes=notes,
        run_head_sensor=run_head_sensor,
        run_camera=run_camera,
        run_arduino_daq=run_arduino_daq,
        run_stim_board=run_stim_board,
        channel_list=channel_list  # Pass our channel list here
    )
