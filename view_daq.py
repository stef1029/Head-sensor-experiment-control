import h5py
import numpy as np
import matplotlib.pyplot as plt

def plot_head_sensor_sync_signal(arduino_daq_h5_path, channel_name="CAMERA"):
    """
    Plots the head sensor sync signal recorded by the ArduinoDAQ on a specified channel.
    
    Args:
        arduino_daq_h5_path (str): Path to the ArduinoDAQ .h5 file.
        channel_name (str): Name of the channel storing the sync signal.
    """
    # Open the HDF5 file
    with h5py.File(arduino_daq_h5_path, 'r') as daq_h5:
        # Load the channel data and timestamps
        camera_data = np.array(daq_h5['channel_data'][channel_name])
        daq_timestamps = np.array(daq_h5['timestamps'])

    # Create the plot
    plt.figure(figsize=(10, 5))
    plt.plot(daq_timestamps, camera_data, label=f'Sync signal ({channel_name})')
    
    # Decorate the plot
    plt.title('ArduinoDAQ Head Sensor Sync Signal')
    plt.xlabel('Time (s)')
    plt.ylabel('Signal')
    plt.legend()
    plt.tight_layout()
    plt.show()

def main():
    # === Fill in these variables ===
    # Provide the path to your ArduinoDAQ .h5 file
    arduino_daq_h5_path = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output\250114_154451_test1\250114_154451_test1-ArduinoDAQ.h5"
    # Provide the channel name for the head sensor sync signal (default is "CAMERA")
    channel_name = "CAMERA"

    # Call the plotting function
    plot_head_sensor_sync_signal(arduino_daq_h5_path, channel_name)

if __name__ == "__main__":
    main()
