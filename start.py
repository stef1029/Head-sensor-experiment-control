from datetime import datetime

from utils.experiment_control_class import ExperimentControl

if __name__ == "__main__":
    output_folder = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output"
    config_path = r"C:\dev\projects\head_sensor_config.json"

    mouse_id = "test"

    # Initialize experiment control
    experiment = ExperimentControl(config_path)

    # Configure COM ports - ADJUST THESE AS NEEDED
    experiment.configure_ports(
        stim_port='COM23',   # Stim board
        head_port='COM24',   # Head sensor
        daq_port='COM18'     # Arduino DAQ
    )

    # Run the experiment with custom parameters including rotation angle
    experiment.run_experiment(
        output_folder=output_folder,
        mouse_id=mouse_id,           
        stim_times_ms=[50, 100, 250, 500, 1000, 2000], 
        num_cycles=20,                   
        stim_delay="5s",
        rotation_angle=90  # set rotation of board on mouse's head
    )