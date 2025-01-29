from datetime import datetime

from utils.experiment_control_class import ExperimentControl

if __name__ == "__main__":
    config_path = r"C:\dev\projects\head_sensor_config.json"

    """
    Set mouse ID and implanted fiber tranmission efficiency (TE) here
    """

    # mouse_id = "mtap16-2a" # left fiber 88%, right 89% - 1.72mW, 5.1, 8.6, 17.21
    # fiber_TE = 88
    # fiber_TE = 89

    # mouse_id = "mtap16-2b" # left fiber 86%, right 87% 
    # fiber_TE = 86
    # fiber_TE = 87

    # mouse_id = "mtaq15-1b" # fiber TE=96%
    # fiber_TE = 96

    mouse_id = "test"
    fiber_TE = 88

    # measured laser power at end of patch cord/ computer laser power (%)
    patch_cord_TE = 66  

    """
    -------------- Set experiment parameters here ----------------------------------------------------------------
    """
    # output_folder = r"D:\2501-Pitx2_opto_inhib_headsensor"     # Output folder for data
    output_folder = r"D:\2701_Pitx2_opto_excite_headsensor"

    at_brain_power_levels = [0.5, 1, 3, 5]              # mW, stimulation intensities to use.
    stim_times_ms = [250, 500, 1000]                # ms, stimulation pulse times to use.
    num_cycles = 1                                     # number of cycles of stim times for each power level.
    stim_delay = 2000                                  # ms, delay between stimulation pulses.
    pulse_freq = 10                                    # Hz, frequency of stimulation pulses. (set at 0 to do solid pulse)
    pulse_on_time = 50                                 # ms, duration of each pulse. 
    # Head sensor rotation angle:
    rotation_angle = 90

    notes = ""

    """
    -------------- End of parameter setup. -----------------------------------------------------------------------
    """

    # Initialize experiment control
    experiment = ExperimentControl(config_path)

    # Configure COM ports - ADJUST THESE AS NEEDED
    experiment.configure_ports(
        stim_port='COM23',   # Stim board
        head_port='COM24',   # Head sensor
        daq_port='COM16'     # Arduino DAQ
    )
    # Turn items in experiment on/off
    run_head_sensor = True
    run_camera = True
    run_arduino_daq = True
    run_stim_board = True           # if stim board off then experiment only ends when Esc pressed.

    # Calculate laser intensities to use to achieve desired stim intensity at brain:
    comp_power_levels = [round((power/(fiber_TE/100))/(patch_cord_TE/100), 1) for power in at_brain_power_levels]

    # Run the experiment with custom parameters including rotation angle
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
        run_stim_board=run_stim_board
    )