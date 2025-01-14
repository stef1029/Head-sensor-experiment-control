"""
This analysis script is in charge of taking the head sensor messages and syncing them up with the pulse times from the arduinoDAQ.
To do this, we first need to find all the pulse times on the appropriate channel, and then find the corresponding number message from the head sensor data.
I then want to save this data as a new dataset with the appropriate timings attached.

grab files from output folder
open arduinodaq h5 file and grab dataset for head sensor pulses
find pulse times
open head sensor data h5 file and grab list of messageIDs
make dict of pulse times and use messageIDs to grab timestamps and make a new dataset of timestamps and data
you now have a dataset of timestamps and data which will line up with the other channels recorded. 

"""

import os
import json
import numpy as np
import h5py
import traceback
from pathlib import Path

from cohort_folder_openfield import Cohort_folder_openfield

class Analysis_manager_openfield:
    """
    Syncs head sensor message IDs from a second HDF5 file with 
    ArduinoDAQ pulse times recorded on the 'CAMERA' channel.
    Produces a dictionary (or other structure) with the synced 
    timestamps and data for further analysis or saving.
    """

    def __init__(self, session_dict):
        """
        Args:
            session_dict (dict): Dictionary containing session information
                                 returned by 'get_session'. Example schema:
                {
                    "session_id": "230101_120000_mouseX",
                    "directory": "/path/to/session_folder",
                    "raw_data": {
                        "arduino_daq_h5": "/path/to/ArduinoDAQ.h5",
                        "head_sensor_h5": "/path/to/HeadSensorData.h5",
                        ...
                    },
                    "processed_data": { ... },
                    ...
                }
        """
        # Basic attributes
        self.session_id = session_dict.get("session_id")
        self.session_dir = Path(session_dict.get("directory", ""))

        # Retrieve file paths from "raw_data" dict
        raw_data = session_dict.get("raw_data", {})
        self.arduino_daq_h5 = Path(raw_data.get("arduino_daq_h5", ""))
        self.head_sensor_h5 = Path(raw_data.get("head_sensor_h5", ""))

        # Run the main sync function
        try:
            self.sync_data = self.sync_head_sensor_with_daq()
            self.save_synced_data(self.sync_data)
        except Exception as e:
            print(f"Error syncing head sensor data for {self.session_dir}: {e}")
            traceback.print_exc()

    def sync_head_sensor_with_daq(self):
        """
        Loads the pulse times from the ArduinoDAQ on the CAMERA channel 
        and matches them to the messageIDs found in the head-sensor data file.

        Returns:
            dict: A dictionary with matched timestamps and sensor data.
        """
        print("Loading ArduinoDAQ pulses from CAMERA channel...")
        with h5py.File(self.arduino_daq_h5, 'r') as daq_h5:
            # channel_data["CAMERA"]: array of 0/1 pulses
            camera_data = np.array(daq_h5['channel_data']['CAMERA'])
            daq_timestamps = np.array(daq_h5['timestamps'])

        # Detect low-to-high transitions in the CAMERA channel.
        # These are your "sync pulses"
        pulse_indices = np.where((camera_data[:-1] == 0) & (camera_data[1:] == 1))[0]
        # The pulse occurs at index+1
        pulse_times = daq_timestamps[pulse_indices + 1]
        print(f"Found {len(pulse_times)} pulses in ArduinoDAQ for CAMERA channel.")

        # 2) Load messageIDs and sensor data from the head sensor HDF5
        #    As saved by your 'save_data' function
        print("Loading head sensor data (message IDs, yaw, pitch, roll)...")
        with h5py.File(self.head_sensor_h5, 'r') as sensor_h5:
            # According to your 'save_data' function, these are stored at the root
            message_ids = np.array(sensor_h5['message_ids'])
            yaw_data    = np.array(sensor_h5['yaw_data'])
            roll_data   = np.array(sensor_h5['roll_data'])
            pitch_data  = np.array(sensor_h5['pitch_data'])
            sensor_ts   = np.array(sensor_h5['timestamps'])

        # 3) Build dictionary of pulse_id -> pulse_time
        #    If message IDs correspond 1:1 to "index in pulses", 
        #    we can do a direct mapping. Otherwise, you need more logic here.
        pulse_dict = {}
        for i, pulse_time in enumerate(pulse_times):
            pulse_dict[i] = pulse_time

        # 4) For each message_id, find the matching pulse timestamp
        #    If your message IDs are exactly 0,1,2,... you can do pulse_dict[msg_id].
        #    If not, you'll need to handle missing pulse_dict keys or offset them.
        print("Syncing head sensor message IDs to pulse timestamps...")
        synced_timestamps = []
        for msg_id in message_ids:
            # pulse_dict.get(...) returns None if the key doesn't exist
            synced_timestamps.append(pulse_dict.get(msg_id, None))

        # Build final dictionary
        synced_data = {
            "session_id": self.session_id,
            "pulse_times": pulse_times.tolist(),
            "message_ids": message_ids.tolist(),
            "yaw_data": yaw_data.tolist(),
            "roll_data": roll_data.tolist(),
            "pitch_data": pitch_data.tolist(),
            "head_sensor_timestamps": sensor_ts.tolist(),
            "synced_timestamps": synced_timestamps,
        }

        return synced_data

    def save_synced_data(self, synced_data):
        """
        Example saving function. Currently saves to JSON for demonstration.
        You can revise to save a new HDF5 if desired.
        """
        print("Saving synced data to JSON for demonstration purposes...")
        output_path = self.session_dir / f"{self.session_id}_head_sensor_synced.json"
        try:
            with open(output_path, 'w') as fp:
                json.dump(synced_data, fp, indent=4)
            print(f"Synced head sensor data saved to {output_path}")
        except Exception as e:
            print(f"Failed to save synced data: {e}")
def main():
    """
    Example main function: 
    - Create session_info 
    - Run the sync.
    """
    cohort_folder = r"C:\Users\Tripodi Group\Videos\2501 - openfield experiment output"
    cohort_folder = Cohort_folder_openfield(cohort_folder)
    cohort_info = cohort_folder.cohort

    sessions_to_process = []
    for mouse, mouse_data in cohort_info["mice"].items():
        for session in mouse_data["sessions"]:
            session_info = cohort_folder.get_session(session)
            sessions_to_process.append(session_info)

    print("Starting main function...")
    # Run processing
    for session in sessions_to_process:
        processor = Analysis_manager_openfield(session)
    print("Processing complete.")

if __name__ == "__main__":
    main()
