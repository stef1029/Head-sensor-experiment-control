from datetime import datetime

from utils.experiment_control_class import ExperimentControl

if __name__ == "__main__":
    config_path = r"C:\dev\projects\head_sensor_config.json"

    """
    Set mouse ID and implanted fiber transmission efficiency (TE) here
    """
    # mouse_id = "mtaq11-3a"
    # fiber_TE = 80

    # mouse_id = "wtjp247-3a"
    # fiber_TE = 82 # left
    # fiber_TE = 83 # right

    # mouse_id = "wtjp247-3b"
    # fiber_TE = 85 # left
    # fiber_TE = 86 # right

    # mouse_id = "wtjp247-3c"
    # fiber_TE = 85 # left
    # fiber_TE = 84 # right

    # mouse_id = "mtaq16-2a"
    # fiber_TE = 88 # left
    # fiber_TE = 89 # right

    mouse_id = "mtaq16-2b"
    # fiber_TE = 86 # left
    fiber_TE = 87 # right

    # mouse_id = "mtaq16-2c"
    # fiber_TE = 83 # left
    # fiber_TE = 87 # right

    # mouse_id = "mtaq16-2d"
    # fiber_TE = 85 # left
    # fiber_TE = 86 # right


    # mouse_id = "test2"
    # fiber_TE = 94


    # patch_cord_TE = 59 # lynn's value
    patch_cord_TE = 64 # actual value



    """
    -------------- Set experiment parameters here ----------------------------------------------------------------
    """
    # output_folder = r"D:\2104_VM_opto_excite_headsensor"
    # at_brain_power_levels = [1, 3, 5, 10, 15, 20, 30]      
    # stim_times_ms = [50, 100, 250, 500, 1000, 2000, 5000, 10000]    
    # num_cycles = 20
    # stim_delay = 5000
    # pulse_freq = 30
    # pulse_on_time = 10
    # # rotation_angle = 270 # chip forward
    # rotation_angle = 90 # chip backward
    # notes = "mtaq14.4a - VM het, backward chip"

    # output_folder = r"C:\DATA\250416_pitx2_stim_check"
    # at_brain_power_levels = [1, 1.5, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16]      
    # stim_times_ms = [500]    
    # num_cycles = 20
    # stim_delay = 5000
    # pulse_freq = 30
    # pulse_on_time = 10
    # # rotation_angle = 270 # chip forward
    # rotation_angle = 90 # chip backward
    # notes = ""

    output_folder = r"C:\DATA\250423_opto_inhibition_SC_bilateral"
    at_brain_power_levels = [1, 1.5, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16]      
    stim_times_ms = [500, 2000]    
    num_cycles = 20
    stim_delay = 5000
    pulse_freq = 0
    pulse_on_time = 10
    # rotation_angle = 270 # chip forward
    rotation_angle = 90 # chip backward
    notes = "right"

    """
    -------------- Set experiment parameters here ----------------------------------------------------------------
    """
    # output_folder = r"D:\test_output"
    # at_brain_power_levels = [5]      
    # stim_times_ms = [2000]    
    # num_cycles = 5
    # stim_delay = 3000
    # pulse_freq = 0
    # pulse_on_time = 10
    # rotation_angle = 90
    # notes = ""

    """
    -------------- Advanced setup (do not change): -------------------------------------------------
    """
    # Initialize experiment control
    experiment = ExperimentControl(config_path)

    # Configure COM ports - ADJUST THESE AS NEEDED
    experiment.configure_ports(
        stim_port='COM23',
        head_port='COM24',
        daq_port='COM19',
        laser_port='COM26'
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
        channel_list=channel_list 
    )
