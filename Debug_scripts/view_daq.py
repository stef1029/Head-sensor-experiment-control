import h5py
import numpy as np
import matplotlib.pyplot as plt

def plot_multiple_channels(arduino_daq_h5_path, channel_names):
    """
    Plots multiple channels from the ArduinoDAQ data as separate subplots.
    
    Args:
        arduino_daq_h5_path (str): Path to the ArduinoDAQ .h5 file.
        channel_names (list): List of channel names to plot.
    """
    # Open the HDF5 file
    with h5py.File(arduino_daq_h5_path, 'r') as daq_h5:
        # Create figure with subplots
        fig, axes = plt.subplots(len(channel_names), 1, figsize=(12, 3*len(channel_names)))
        
        # Get timestamps once
        daq_timestamps = np.array(daq_h5['timestamps'])
        
        # Handle case of single channel (axes not being array)
        if len(channel_names) == 1:
            axes = [axes]
        
        # Plot each channel
        for ax, channel in zip(axes, channel_names):
            try:
                channel_data = np.array(daq_h5['channel_data'][channel])
                ax.plot(daq_timestamps, channel_data, label=channel)
                ax.set_ylabel('Signal')
                ax.legend(loc='upper right')
                
                # Only show x-label for bottom subplot
                if ax == axes[-1]:
                    ax.set_xlabel('Time (s)')
            except KeyError:
                ax.text(0.5, 0.5, f'Channel "{channel}" not found', 
                       horizontalalignment='center',
                       verticalalignment='center')
                ax.set_ylabel('N/A')
    
    # Add overall title
    plt.suptitle('ArduinoDAQ Signals')
    plt.tight_layout()
    plt.show()

def main():
    # === Fill in these variables ===
    # Provide the path to your ArduinoDAQ .h5 file
    arduino_daq_h5_path = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output\250121_155745_mtaq11-2g\250121_155745_mtaq11-2g-ArduinoDAQ.h5"
    
    # List all channels you want to plot
    channel_names = ["CAMERA_SYNC", "HEADSENSOR_SYNC", "LASER_SYNC"]  # Add or modify channels as needed

    # Call the plotting function
    plot_multiple_channels(arduino_daq_h5_path, channel_names)

if __name__ == "__main__":
    main()