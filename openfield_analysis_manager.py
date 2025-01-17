
import json
import numpy as np
import h5py
import traceback
from pathlib import Path


class Analysis_manager_openfield:
    def __init__(self, session_dict):
        # Basic attributes
        self.session_id = session_dict.get("session_id")
        self.session_dir = Path(session_dict.get("directory", ""))

        # Retrieve file paths from "raw_data" dict
        raw_data = session_dict.get("raw_data", {})
        self.arduino_daq_h5 = Path(raw_data.get("arduino_daq_h5", ""))
        self.head_sensor_h5 = Path(raw_data.get("head_sensor_h5", ""))
        
        # Add path for tracker data JSON
        self.tracker_json = self.session_dir / f"{self.session_id}_Tracker_data.json"

        # Run the main sync functions
        try:
            # Sync both head sensor and camera frame data
            self.sync_data = self.sync_all_data()
            self.save_synced_data(self.sync_data)
        except Exception as e:
            print(f"Error syncing data for {self.session_dir}: {e}")
            traceback.print_exc()

    def get_sync_pulses(self, channel_name):
        """
        Helper function to get sync pulses for a given channel from ArduinoDAQ.
        
        Args:
            channel_name (str): Name of the channel in ArduinoDAQ file
            
        Returns:
            tuple: (pulse_times, timestamps from DAQ)
        """
        with h5py.File(self.arduino_daq_h5, 'r') as daq_h5:
            channel_data = np.array(daq_h5['channel_data'][channel_name])
            daq_timestamps = np.array(daq_h5['timestamps'])

        # Detect low-to-high transitions
        pulse_indices = np.where((channel_data[:-1] == 0) & (channel_data[1:] == 1))[0]
        # The pulse occurs at index+1
        pulse_times = daq_timestamps[pulse_indices + 1]
        
        print(f"Found {len(pulse_times)} pulses in ArduinoDAQ for {channel_name} channel.")
        return pulse_times, daq_timestamps

    def sync_head_sensor_data(self, pulse_times):
        """
        Sync head sensor data with DAQ pulse times.
        """
        with h5py.File(self.head_sensor_h5, 'r') as sensor_h5:
            message_ids = np.array(sensor_h5['message_ids'])
            yaw_data = np.array(sensor_h5['yaw_data'])
            roll_data = np.array(sensor_h5['roll_data'])
            pitch_data = np.array(sensor_h5['pitch_data'])
            sensor_ts = np.array(sensor_h5['timestamps'])

        # Build pulse dictionary
        pulse_dict = {i: pulse_time for i, pulse_time in enumerate(pulse_times)}

        # Sync timestamps
        print("Syncing head sensor message IDs to pulse timestamps...")
        synced_timestamps = [pulse_dict.get(msg_id, None) for msg_id in message_ids]

        return {
            "message_ids": message_ids.tolist(),
            "yaw_data": yaw_data.tolist(),
            "roll_data": roll_data.tolist(),
            "pitch_data": pitch_data.tolist(),
            "head_sensor_timestamps": sensor_ts.tolist(),
            "synced_timestamps": synced_timestamps,
        }

    def sync_camera_data(self, pulse_times):
        """
        Sync camera frame IDs with DAQ pulse times.
        """
        # Load frame IDs from tracker JSON
        try:
            with open(self.tracker_json, 'r') as f:
                tracker_data = json.load(f)
                frame_ids = np.array(tracker_data["frame_IDs"])
        except Exception as e:
            print(f"Error loading tracker data: {e}")
            return None

        # Build pulse dictionary
        pulse_dict = {i: pulse_time for i, pulse_time in enumerate(pulse_times)}

        # Sync timestamps
        print("Syncing camera frame IDs to pulse timestamps...")
        synced_timestamps = [pulse_dict.get(frame_id, None) for frame_id in frame_ids]

        return {
            "frame_ids": frame_ids.tolist(),
            "synced_timestamps": synced_timestamps,
        }

    def sync_all_data(self):
        """
        Sync both head sensor and camera frame data with their respective pulses.
        """
        # Get pulse times for both channels
        head_sensor_pulses, _ = self.get_sync_pulses('HEADSENSOR_SYNC')
        camera_pulses, _ = self.get_sync_pulses('CAMERA_SYNC')

        # Sync head sensor data
        head_sensor_data = self.sync_head_sensor_data(head_sensor_pulses)
        
        # Sync camera frame data
        camera_data = self.sync_camera_data(camera_pulses)

        # Combine all synced data
        synced_data = {
            "session_id": self.session_id,
            "head_sensor": {
                "pulse_times": head_sensor_pulses.tolist(),
                **head_sensor_data
            },
            "camera": {
                "pulse_times": camera_pulses.tolist(),
                **camera_data
            } if camera_data is not None else None
        }

        return synced_data

    def save_synced_data(self, synced_data):
        """
        Save the synced data to JSON.
        """
        print("Saving synced data...")
        output_path = self.session_dir / f"{self.session_id}_synced_data.json"
        try:
            with open(output_path, 'w') as fp:
                json.dump(synced_data, fp, indent=4)
            print(f"Synced data saved to {output_path}")
        except Exception as e:
            print(f"Failed to save synced data: {e}")